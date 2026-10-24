'use strict';

// 引擎在浏览器内由 Pyodide 运行同一份 bazi_engine.py；本文件只负责收集输入与显示结果。
const $ = (s) => document.querySelector(s);
const form = $('#f');
const go = $('#go');
const statusEl = $('#status');
let mode = 'birth';
let py = null;
let last = null;

const BRIDGE = `
import json
from bazi_engine import solve, read_json, load_terms, render_markdown, RulebookError, DEFAULT_TERMS
_R = read_json('rules.json')
_T = load_terms(DEFAULT_TERMS)

def run(req_json):
    try:
        res = solve(json.loads(req_json), _R, _T)
        return json.dumps({'ok': True, 'markdown': render_markdown(res), 'result': res}, ensure_ascii=False, default=str)
    except RulebookError as e:
        return json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)
`;

async function boot() {
  try {
    statusEl.textContent = '下载 Python 运行时（首次约 10 MB）…';
    py = await loadPyodide();
    const manifest = await (await fetch('engine/manifest.json', { cache: 'no-cache' })).json();
    for (const f of manifest.files) {
      const res = await fetch(`engine/${f}?v=${manifest.sha256}`);
      if (!res.ok) throw new Error(`无法加载 ${f}`);
      py.FS.writeFile(`/home/pyodide/${f}`, new Uint8Array(await res.arrayBuffer()));
    }
    py.runPython(BRIDGE);
    $('#ver').textContent = `引擎 ${manifest.engine_version} · 规则表 ${manifest.rules_version} · ${manifest.sha256} · ${manifest.tests}`;
    go.disabled = false;
    go.textContent = '计算';
    statusEl.textContent = '引擎就绪';
  } catch (e) {
    statusEl.textContent = `引擎加载失败：${e.message}`;
    go.textContent = '不可用';
  }
}

function setMode(m) {
  mode = m;
  document.querySelectorAll('#form-card .tab').forEach((b) => b.classList.toggle('active', b.dataset.mode === m));
  document.querySelectorAll('[class*="mode-"]').forEach((el) => {
    el.hidden = !el.className.split(/\s+/).includes(`mode-${m}`);
  });
}

function tzMeridian(tz) {
  const [h, mi] = tz.slice(1).split(':').map(Number);
  return (tz[0] === '-' ? -1 : 1) * (h + mi / 60) * 15;
}

function buildRequest() {
  const v = Object.fromEntries(new FormData(form).entries());
  if (mode === 'pillars') {
    const p = { year: v.py.trim(), month: v.pm.trim(), day: v.pd.trim(), hour: v.ph.trim() };
    if (Object.values(p).some((x) => x.length !== 2)) throw new Error('四柱每柱需两个汉字，例如 乙酉');
    return { pillars: p };
  }
  const req = {
    calendar_policy: 'solar_jie',
    day_boundary: v.day_boundary,
    late_zi_hour_stem: v.late_zi,
    clock_mode: v.clock_mode,
    wangxiang_policy: v.wx,
  };
  if (v.clock_mode === 'mean_solar') {
    req.longitude_deg_east = Number(v.lon);
    req.reference_meridian_deg_east = tzMeridian(v.tz);
  }
  if (mode === 'birth') {
    req.birth_time = `${v.date}T${v.time}:00${v.tz}`;
  } else {
    if (!v.range_start || !v.range_end) throw new Error('请填写时间区间的起止');
    req.birth_time_range = { start: `${v.range_start}:00${v.tz}`, end: `${v.range_end}:00${v.tz}` };
  }
  if (v.gender) {
    req.gender = v.gender;
    req.luck_policy = 'LUCK-P1';
  }
  return req;
}

function show(view) {
  document.querySelectorAll('#out .tab').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
  $('#report').hidden = view !== 'report';
  $('#json').hidden = view !== 'json';
}

function download(name, text, type) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

form.addEventListener('submit', (ev) => {
  ev.preventDefault();
  if (!py) return;
  let req;
  try {
    req = buildRequest();
  } catch (e) {
    statusEl.textContent = e.message;
    return;
  }
  const t0 = performance.now();
  const out = JSON.parse(py.globals.get('run')(JSON.stringify(req)));
  if (!out.ok) {
    statusEl.textContent = `输入不足或不合规则：${out.error}`;
    $('#out').hidden = true;
    return;
  }
  last = out;
  $('#report').innerHTML = DOMPurify.sanitize(marked.parse(out.markdown));
  $('#json').textContent = JSON.stringify(out.result, null, 2);
  $('#out').hidden = false;
  show('report');
  statusEl.textContent = `完成（${Math.round(performance.now() - t0)} ms，本地计算）`;
  $('#out').scrollIntoView({ behavior: 'smooth', block: 'start' });
});

document.querySelectorAll('#form-card .tab').forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
document.querySelectorAll('#out .tab').forEach((b) => b.addEventListener('click', () => show(b.dataset.view)));
form.clock_mode.addEventListener('change', () => {
  document.querySelectorAll('.needs-mean').forEach((el) => { el.hidden = form.clock_mode.value !== 'mean_solar'; });
});
$('#dl-md').addEventListener('click', () => last && download('bazi_report.md', last.markdown, 'text/markdown'));
$('#dl-json').addEventListener('click', () => last && download('bazi_result.json', JSON.stringify(last.result, null, 2), 'application/json'));

setMode('birth');
form.clock_mode.dispatchEvent(new Event('change'));
boot();
