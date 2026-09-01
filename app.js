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

// экранирование для вставки имён в html
function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// имена как редактируемые ячейки (contenteditable)
function editableNames(asgn, slotKey) {
  const names = asgn[slotKey] || [];
  if (!names.length) return '—';
  return names.map((n, i) =>
    `<span class="editable-name" contenteditable="true" spellcheck="false" data-slot="${slotKey}" data-i="${i}">${escapeHtml(n)}</span>`
  ).join(',<br>');
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
_json.dumps({"xlsx": r["xlsx"], "assignment": r["assignment"], "promoted": r.get("promoted", [])})
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
      + '<th style="' + thStyle() + '">Позиция</th>'
      + '<th style="' + thStyle() + '; background:#D9E6F2;">ПРОП</th>'
      + '<th style="' + thStyle() + '; background:#FBF2CC;">ОПП</th>'
      + '</tr></thead><tbody>';
    const posNames = { 1: '1 стол', 2: '2 стол' };
    const roomNames = { 1: 'Верхний рум (вы здесь)', 2: 'Подвал' };
    for (const room of [1, 2]) {
      for (const pos of [1, 2]) {
        const prop = editableNames(asgn, `${room}_${pos}_ПРОП`);
        const opp  = editableNames(asgn, `${room}_${pos}_ОПП`);
        html += '<tr>';
        if (pos === 1) html += `<td rowspan="2" style="${tdStyle(true)}">${room}</td>`;
        html += `<td style="${tdStyle()}">${posNames[pos]}</td>`;
        html += `<td style="${tdStyle()}; background:#EEF4FA;">${prop}</td>`;
        html += `<td style="${tdStyle()}; background:#FEFAED;">${opp}</td>`;
        html += '</tr>';
      }
    }
    html += '</tbody></table>';
    if (parsed.promoted && parsed.promoted.length) {
      html += '<p style="font-size: 13px; color: var(--muted); margin-top: 12px; text-align: center;">'
        + 'Для заполнения сетки автоматически назначены айронами: <b>'
        + parsed.promoted.map(escapeHtml).join(', ') + '</b></p>';
    }
    document.getElementById('draw-table').innerHTML = html;
    // прячем старую картинку подготовки — она относилась к прошлой жеребьёвке
    const prepArea = document.getElementById('prep-image-area');
    if (prepArea) prepArea.style.display = 'none';
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
// === Места подготовки ===

// Enter внутри редактируемого имени не должен создавать перенос строки
document.getElementById('draw-table').addEventListener('keydown', (e) => {
  if (e.target.classList && e.target.classList.contains('editable-name') && e.key === 'Enter') {
    e.preventDefault();
    e.target.blur();
  }
});

// собираем актуальные (в т.ч. отредактированные) имена по позиции и стороне
function collectByPosition() {
  const map = { '1_ПРОП': [], '2_ПРОП': [], '1_ОПП': [], '2_ОПП': [] };
  document.querySelectorAll('#draw-table .editable-name').forEach(sp => {
    const parts = (sp.dataset.slot || '').split('_'); // room_pos_side
    if (parts.length !== 3) return;
    const key = `${parts[1]}_${parts[2]}`;
    const name = sp.textContent.trim();
    if (name && map[key]) map[key].push(name);
  });
  return map;
}

// рисуем картинку "Где готовимся" на канвасе
function drawPrepImage(byPos) {
  // раскладка: бар и большой зал переставлены, малый зал и склад тоже (зеркально по горизонтали)
  const cells = [
    { row: 0, col: 0, place: 'Большой зал', names: byPos['2_ПРОП'] },
    { row: 0, col: 1, place: 'Бар',         names: byPos['1_ПРОП'] },
    { row: 1, col: 0, place: 'Склад',       names: byPos['2_ОПП'] },
    { row: 1, col: 1, place: 'Малый зал',   names: byPos['1_ОПП'] },
  ];
  const sideLabels = ['Верх', 'Низ'];

  const scale = 2; // ретина-чёткость
  const pad = 16, titleH = 44, sideW = 52;
  const labelH = 22, lineH = 26, cellPad = 8;

  // ширина ячейки подстраивается под самое длинное имя
  const measurer = document.createElement('canvas').getContext('2d');
  measurer.font = "600 19px 'Fira Sans', Arial, sans-serif";
  let maxNameW = 0;
  for (const c of cells) for (const n of c.names) {
    maxNameW = Math.max(maxNameW, measurer.measureText(n).width);
  }
  const cellW = Math.min(360, Math.max(220, Math.ceil(maxNameW) + cellPad * 2 + 8));

  const maxLines = Math.max(1, ...cells.map(c => c.names.length));
  const cellH = labelH + cellPad + maxLines * lineH + cellPad;
  const width = pad * 2 + cellW * 2 + sideW;
  const height = pad + titleH + cellH * 2 + pad;

  const canvas = document.createElement('canvas');
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext('2d');
  ctx.scale(scale, scale);

  // фон
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);
  ctx.textBaseline = 'top';
  ctx.fillStyle = '#111111';

  // заголовок
  ctx.font = "600 26px 'Fira Sans', Arial, sans-serif";
  ctx.fillText('Где готовимся', pad, pad);

  const gridX = pad, gridY = pad + titleH;

  // ячейки
  for (const c of cells) {
    const x = gridX + c.col * cellW;
    const y = gridY + c.row * cellH;
    ctx.strokeStyle = '#111111';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(x, y, cellW, cellH);

    // подпись места
    ctx.font = "400 14px 'Fira Sans', Arial, sans-serif";
    ctx.fillStyle = '#333333';
    ctx.fillText(c.place, x + cellPad, y + 5);

    // имена
    ctx.font = "600 19px 'Fira Sans', Arial, sans-serif";
    ctx.fillStyle = '#111111';
    if (c.names.length) {
      c.names.forEach((n, i) => {
        // подрезаем слишком длинные имена, чтобы не вылезали за ячейку
        let text = n;
        while (ctx.measureText(text).width > cellW - cellPad * 2 && text.length > 3) {
          text = text.slice(0, -2);
        }
        if (text !== n) text += '…';
        ctx.fillText(text, x + cellPad, y + labelH + cellPad + i * lineH);
      });
    } else {
      ctx.fillStyle = '#999999';
      ctx.fillText('—', x + cellPad, y + labelH + cellPad);
    }
  }

  // подписи Верх / Низ справа
  ctx.font = "400 15px 'Fira Sans', Arial, sans-serif";
  ctx.fillStyle = '#111111';
  sideLabels.forEach((lbl, row) => {
    ctx.fillText(lbl, gridX + cellW * 2 + 10, gridY + row * cellH + 4);
  });

  return canvas;
}

const showPrepBtn = document.getElementById('show-prep');
if (showPrepBtn) {
  showPrepBtn.addEventListener('click', async () => {
    try { await document.fonts.ready; } catch {}
    const canvas = drawPrepImage(collectByPosition());
    const dataURL = canvas.toDataURL('image/png');
    const img = document.getElementById('prep-img');
    const link = document.getElementById('prep-download');
    img.src = dataURL;
    link.href = dataURL;
    const area = document.getElementById('prep-image-area');
    area.style.display = 'block';
    area.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
}
