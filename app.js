// 16 колонок для участников 
const rowsContainer = document.getElementById('rows');
for (let i = 1; i <= 16; i++) {
  const row = document.createElement('div');
  row.className = 'row';
  row.dataset.idx = i;
  row.innerHTML = `
    <div class="num">${i}</div>
    <input type="text" class="name" placeholder="${i === 1 ? 'Имя участника' : ''}" autocomplete="off">
    <div class="cell-level">
      <span class="m-lbl">Уровень</span>
      <select class="level">
        <option value="oldman" selected>Старичок</option>
        <option value="newbie">Новичок</option>
      </select>
    </div>
    <div class="cell-iron">
      <span class="m-lbl">Айрон</span>
      <select class="iron">
        <option value="0">Нет</option>
        <option value="1">Да</option>
      </select>
    </div>
    <div class="opening-cell">
      <select class="opening">
        <option value="0">Без предпочтения</option>
        <option value="1">Только первые столы</option>
      </select>
    </div>
  `;
  rowsContainer.appendChild(row);
  row.querySelector('.iron').addEventListener('change', (e) => {
    if (e.target.value === '1') row.classList.add('has-iron');
    else { row.classList.remove('has-iron'); row.querySelector('.opening').value = '0'; }
  });
}

// выбор режима игры
document.querySelectorAll('.mode-card').forEach(card => {
  card.addEventListener('click', () => {
    document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    card.querySelector('input').checked = true;
  });
});

// вспомогалка
const statusEl = document.getElementById('status');
const errorEl = document.getElementById('error-msg');
const submitBtn = document.getElementById('submit');

function setStatus(text, kind) {
  statusEl.className = 'status' + (kind ? ' ' + kind : '');
  statusEl.innerHTML = (kind === 'ready' ? '' : '<div class="spinner"></div>') + '<span>' + text + '</span>';
}
function showError(msg) {
  errorEl.textContent = msg;
  errorEl.classList.add('visible');
}
function clearError() { errorEl.classList.remove('visible'); }

// загрузка пиодиди
let pyodide = null;
async function boot() {
  try {
    setStatus('Загружаю Python в браузер...');
    pyodide = await loadPyodide();
    setStatus('Устанавливаю openpyxl...');
    await pyodide.loadPackage('micropip');
    await pyodide.runPythonAsync(`
import micropip
await micropip.install('openpyxl')
    `);
    setStatus('Загружаю алгоритм...');
        const pkgFiles = [
        'bpd/__init__.py',
        'bpd/models.py',
        'bpd/algorithm.py',
        'bpd/excel.py',
        'bpd/entrypoint.py',
        ];
        pyodide.FS.mkdir('bpd');
        for (const path of pkgFiles) {
        const resp = await fetch(path);
        if (!resp.ok) throw new Error(`Не удалось загрузить ${path} (${resp.status})`);
        const code = await resp.text();
        pyodide.FS.writeFile(path, code);
        }
        pyodide.runPython('from bpd import run_draw');
    setStatus('Готово — заполняйте форму', 'ready');
    submitBtn.disabled = false;
  } catch (e) {
    setStatus('Ошибка загрузки: ' + e.message, 'error');
  }
}
boot();

// проверка данных
function gather() {
  const participants = [];
  document.querySelectorAll('.row').forEach(row => {
    const name = row.querySelector('.name').value.trim();
    if (!name) return;
    const level = row.querySelector('.level').value;
    const ironman = row.querySelector('.iron').value === '1';
    const opening = parseInt(row.querySelector('.opening').value, 10);
    if (!level) throw new Error(`Участник «${name}» — не выбран уровень`);
    participants.push({ name, level, ironman, opening: ironman ? opening : 0 });
  });
  if (participants.length < 2) throw new Error('Нужно как минимум 2 участника');
  const mode = parseInt(document.querySelector('input[name="mode"]:checked').value, 10);
  const ironCount = participants.filter(p => p.ironman).length;
  const capacity = 16 - ironCount;
  if (participants.length > capacity) {
    throw new Error(`Слишком много участников (${participants.length}) при ${ironCount} айронах — максимум ${capacity}`);
  }
  return { participants, mode };
}

// рендер итоговой таблицы
function thStyle(align) {
  return `padding: 8px 12px; border: 1px solid var(--hairline); text-align: ${align || 'center'}; font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;`;
}
function tdStyle(center) {
  return `padding: 10px 12px; border: 1px solid var(--hairline); text-align: ${center ? 'center' : 'left'}; vertical-align: middle;`;
}

// сабмит кнопка
submitBtn.addEventListener('click', async () => {
  clearError();
  if (!pyodide) return;
  let data;
  try { data = gather(); }
  catch (e) { showError(e.message); return; }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Считаю...';
  try {
    pyodide.globals.set('input_json', JSON.stringify(data.participants));
    const result = pyodide.runPython(`
import json
r = run_draw(json.loads(input_json), ${data.mode})
import json as _json
_json.dumps({"xlsx": r["xlsx"], "assignment": r["assignment"]})
    `);
    const parsed = JSON.parse(result);

    const bytes = new Uint8Array(parsed.xlsx);
    const blob = new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'bp_draw.xlsx';
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    const asgn = parsed.assignment;
    let html = '<table style="width:100%; border-collapse:collapse; font-size:14px;">';
    html += '<thead><tr>'
      + '<th style="' + thStyle('left') + '">Рум</th>'
      + '<th style="' + thStyle() + '">Поз.</th>'
      + '<th style="' + thStyle() + '; background:#D9E6F2;">ПРОП</th>'
      + '<th style="' + thStyle() + '; background:#FBF2CC;">ОПП</th>'
      + '</tr></thead><tbody>';
    const roomNames = { 1: 'Верхний рум (вы здесь)', 2: 'Подвал' };
    for (const room of [1, 2]) {
      for (const pos of [1, 2]) {
        const prop = (asgn[`${room}_${pos}_ПРОП`] || []).join(',<br>') || '—';
        const opp  = (asgn[`${room}_${pos}_ОПП`]  || []).join(',<br>') || '—';
        html += '<tr>';
        if (pos === 1) html += `<td rowspan="2" style="${tdStyle(true)}">${room}</td>`;
        html += `<td style="${tdStyle()}">${pos}</td>`;
        html += `<td style="${tdStyle()}; background:#EEF4FA;">${prop}</td>`;
        html += `<td style="${tdStyle()}; background:#FEFAED;">${opp}</td>`;
        html += '</tr>';
      }
    }
    html += '</tbody></table>';
    document.getElementById('draw-table').innerHTML = html;
    const section = document.getElementById('result-section');
    section.style.display = 'block';
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch (e) {
    showError('Ошибка при генерации: ' + (e.message || e));
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Сгенерировать таблицу';
  }
});

// парсер имен из url
function parseNamesText(raw) {
  return raw.split(/[\n,;]+/).map(s => s.trim()).filter(Boolean);
}

function fillNameFields(names) {
  document.querySelectorAll('.row .name').forEach((input, i) => {
    input.value = names[i] || '';
  });
}

function buildShareURL() {
  const names = Array.from(document.querySelectorAll('.row .name'))
    .map(i => i.value.trim())
    .filter(Boolean);
  const base = window.location.origin + window.location.pathname;
  if (!names.length) return base;
  return base + '?names=' + encodeURIComponent(names.join(','));
}

// автозаполнение из юрл
(function loadFromURL() {
  const params = new URLSearchParams(window.location.search);
  const namesParam = params.get('names');
  if (!namesParam) return;
  const names = parseNamesText(namesParam);
  fillNameFields(names);
})();

// вставка имен (экспериментально)
const applyBtn = document.getElementById('apply-paste');
if (applyBtn) {
  applyBtn.addEventListener('click', () => {
    const names = parseNamesText(document.getElementById('paste-names').value);
    if (names.length) fillNameFields(names);
  });
}

const copyBtn = document.getElementById('copy-link');
if (copyBtn) {
  copyBtn.addEventListener('click', async () => {
    const url = buildShareURL();
    try {
      await navigator.clipboard.writeText(url);
      const old = copyBtn.textContent;
      copyBtn.textContent = 'Скопировано';
      setTimeout(() => copyBtn.textContent = old, 1500);
    } catch {
      prompt('Скопируйте ссылку:', url);
    }
  });
}