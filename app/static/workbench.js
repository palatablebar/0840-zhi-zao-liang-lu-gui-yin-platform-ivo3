(function () {
  var state = { payload: null, kind: 'bars', run: null, approved: false };
  var $ = function (id) { return document.getElementById(id); };
  // 成品扣货排查示例：可疑料拆分、干净线混装与一笔可补齐的交接
  var HOLD_SAMPLE = {
    investigation_id: 'INV-DEMO-01',
    suspect: { stage: '冲压', material_batch: 'MB-BAD' },
    work_reports: [
      { report_id: 'W1', stage: '冲压', stage_seq: 1,
        inputs: [{ batch: 'MB-BAD', qty: 100 }],
        outputs: [{ batch: 'S1', qty: 60 }, { batch: 'S2', qty: 40 }] },
      { report_id: 'W2', stage: '冲压', stage_seq: 1,
        inputs: [{ batch: 'MB-OK', qty: 100 }],
        outputs: [{ batch: 'S3', qty: 100 }] },
      { report_id: 'W3', stage: '焊接', stage_seq: 2,
        inputs: [{ batch: 'S1', qty: 60 }, { batch: 'S3', qty: 40 }],
        outputs: [{ batch: 'FG1', qty: 100 }] },
      { report_id: 'W4', stage: '焊接', stage_seq: 2,
        inputs: [{ batch: 'S2', qty: 40 }],
        outputs: [{ batch: 'FG2', qty: 40 }] },
      { report_id: 'W5', stage: '冲压', stage_seq: 1,
        inputs: [{ batch: 'MB-CLEAN', qty: 80 }],
        outputs: [{ batch: 'S4', qty: 80 }] },
      { report_id: 'W6', stage: '焊接', stage_seq: 2,
        inputs: [{ batch: 'S4', qty: 80 }],
        outputs: [{ batch: 'FG3', qty: 80 }] }
    ],
    handovers: [
      { handover_id: 'H1', stage: '冲压', stage_seq: 1, from_qty: 280, to_qty: 280 }
    ]
  };
  var HOLD_REASON_TEXT = {
    SUSPECT_LINEAGE: '报工血缘追溯到可疑来料',
    MIX_UNVERIFIED: '仅总量一致，混装去向无法排除',
    HANDOVER_MISMATCH: '交接数量对不上，不得放行',
    HANDOVER_MISSING: '交接记录缺失，去向无法证实',
    LINEAGE_GAP: '报工断链，无法证实未混入',
    CLEAN_LINEAGE: '血缘证实未混入，当天照发',
    HANDOVER_CONFIRMED_CLEAN: '补齐交接后证实无涉，恢复放行',
    CLEAR_PATH: '未经过受影响交接，放行'
  };
  function esc(value) {
    return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, function (ch) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch];
    });
  }
  async function request(url, options) {
    var response = await fetch(url, Object.assign({headers: {'Content-Type': 'application/json'}}, options || {}));
    var data = await response.json().catch(function () { return {}; });
    if (!response.ok) throw new Error(data.error || ('HTTP ' + response.status));
    return data;
  }
  function setNotice(text) { $('notice').textContent = text || ''; }
  function renderIssues(data) {
    $('issue-count').textContent = data.issues.length + ' 条';
    $('issue-list').innerHTML = data.issues.length ? data.issues.map(function (item) {
      return '<li><span>' + esc(item.line || '-') + '</span><span>' + esc(item.key || '无主键') + '</span><code>' + esc(item.code) + '</code></li>';
    }).join('') : '<li class="empty">暂无异常</li>';
  }
  function renderBreakdown(items) {
    if (!items || !items.length) return '';
    return '<details><summary>' + items.length + ' 项</summary><ul>' + items.map(function (item) {
      return '<li>' + esc(item) + '</li>';
    }).join('') + '</ul></details>';
  }
  function renderRows(data) {
    var labels = Object.assign({label: '记录'}, state.resultColumns);
    var source = data.row_kind === 'source';
    var hasBreakdown = data.rows.some(function (row) { return row.breakdown && row.breakdown.length; });
    var keys = source ? state.inputColumns : Object.keys(labels).filter(function (key) {
      return data.rows.some(function (row) { return Object.hasOwn(row, key); });
    });
    $('row-count').textContent = source ? data.rows.length + ' 行预览' :
      data.summary.PASS + ' 通过 / ' + data.summary.REVIEW + ' 复核 / ' + data.summary.REJECT + ' 阻断';
    var tail = source ? '' : '<th>结论</th>' + (hasBreakdown ? '<th>计算分项</th>' : '');
    $('row-head').innerHTML = '<tr>' + keys.map(function (key) { return '<th>' + esc(labels[key] || key) + '</th>'; }).join('') + tail + '</tr>';
    $('row-body').innerHTML = data.rows.length ? data.rows.map(function (row) {
      var values = keys.map(function (key) { return '<td class="' + (typeof row[key] === 'number' ? 'num' : '') + '">' + esc(row[key]) + '</td>'; }).join('');
      var verdict = source ? '' : '<td><span class="verdict" data-v="' + esc(row.verdict) + '">' + esc(row.verdict || '') + '</span><br><small>' + esc(row.reason || '') + '</small></td>';
      var breakdown = hasBreakdown ? '<td>' + renderBreakdown(row.breakdown) + '</td>' : '';
      return '<tr>' + values + verdict + breakdown + '</tr>';
    }).join('') : '<tr><td class="empty" colspan="' + (keys.length + (source ? 0 : 1)) + '">没有可展示条目</td></tr>';
  }
  function renderLedger(data) {
    if (!data.ledger) { $('ledger-list').innerHTML = '<p class="empty">运行对账后显示</p>'; return; }
    var values = data.ledger;
    $('ledger-list').innerHTML = [
      ['来源行', values.counts.input], ['采信行', values.counts.accepted], ['隔离行', values.counts.isolated],
      ['精确重复', values.counts.duplicates], ['忽略行', values.counts.ignored], ['计算条目', values.counts.computed]
    ].map(function (row) { return '<div class="ledger-row"><span>' + row[0] + '</span><strong>' + row[1] + '</strong></div>'; }).join('') +
      '<div class="ledger-row"><span>' + esc(values.metric_field) + '</span><strong>' + esc(values.metric_total) + '</strong></div>' +
      values.checks.map(function (check) { return '<div class="ledger-row"><span>' + esc(check.label) + '</span><strong class="' + (check.ok ? 'check-ok' : 'check-bad') + '">' + (check.ok ? '通过' : '异常') + '</strong></div>'; }).join('');
  }
  function render(data) {
    state.payload = data;
    $('chart-label').textContent = Object.values(state.resultColumns)[0];
    $('m-input').textContent = data.counts.input;
    $('m-accepted').textContent = data.counts.accepted;
    $('m-isolated').textContent = data.counts.isolated + data.counts.duplicates;
    $('m-rejected').textContent = data.summary.REJECT;
    renderRows(data);
    renderIssues(data);
    renderLedger(data);
    window.renderChart($('chart'), data.chart && data.chart.length ? (state.kind || 'bars') : 'bars', data.chart || []);
  }
  function stageButtons(stages) {
    $('stage-nav').innerHTML = stages.map(function (stage, index) {
      return '<button type="button" data-stage="' + stage.id + '" aria-pressed="' + (index === 0 ? 'true' : 'false') + '">' + esc(stage.name) + '</button>';
    }).join('');
    Array.from(document.querySelectorAll('[data-stage]')).forEach(function (button) {
      button.addEventListener('click', function () {
        document.querySelectorAll('[data-stage]').forEach(function (other) { other.setAttribute('aria-pressed', String(other === button)); });
        loadStage(button.getAttribute('data-stage'));
      });
    });
  }
  async function loadStage(stage) {
    try {
      setNotice('');
      document.body.setAttribute('aria-busy', 'true');
      var payload = await request('/api/stages/' + stage, {method: 'POST', body: JSON.stringify({profile: $('profile').value})});
      render(payload);
    } catch (error) { setNotice(error.message); }
    finally { document.body.removeAttribute('aria-busy'); }
  }
  async function runBatch() {
    try {
      setNotice('');
      $('run').disabled = true;
      var run = await request('/api/runs', {method: 'POST', body: JSON.stringify({profile: $('profile').value})});
      state.run = run;
      state.approved = run.status === 'APPROVED';
      render(run);
      $('run-status').textContent = run.status + ' · rev ' + run.revision;
      $('revision').textContent = 'rev ' + run.revision;
      $('sign').disabled = run.summary.REJECT > 0 || state.approved;
      $('hold').disabled = state.approved;
      $('download').hidden = !state.approved;
      if (state.approved) $('download').href = '/api/runs/' + run.run_id + '/evidence';
    } catch (error) { setNotice(error.message); }
    finally { $('run').disabled = false; }
  }
  async function review(decision) {
    if (!state.run) return;
    try {
      var run = await request('/api/runs/' + state.run.run_id + '/review', {
        method: 'POST',
        body: JSON.stringify({decision: decision, comment: $('comment').value, expected_revision: state.run.revision})
      });
      state.run = run;
      state.approved = run.status === 'APPROVED';
      $('run-status').textContent = run.status + ' · rev ' + run.revision;
      $('revision').textContent = 'rev ' + run.revision;
      $('sign').disabled = true;
      $('hold').disabled = true;
      $('download').hidden = !state.approved;
      if (state.approved) $('download').href = '/api/runs/' + run.run_id + '/evidence';
    } catch (error) { setNotice(error.message); }
  }
  async function loadHolds() {
    try {
      var data = await request('/api/holds/results');
      $('hold-count').textContent = data.count + ' 批扣货';
      $('hold-body').innerHTML = data.holds.length ? data.holds.map(function (item) {
        return '<tr><td>' + esc(item.investigation_id) + '</td><td>' + esc(item.fg_batch) + '</td>' +
          '<td>' + esc(item.stage) + '</td><td class="num">' + esc(item.qty) + '</td>' +
          '<td><span class="verdict" data-v="' + esc(item.decision) + '">' + esc(item.decision) + '</span></td>' +
          '<td><small>' + esc(HOLD_REASON_TEXT[item.reason] || item.reason) + '</small></td></tr>';
      }).join('') : '<tr><td class="empty" colspan="6">暂无扣货成品</td></tr>';
    } catch (error) { setNotice(error.message); }
  }
  async function runHoldInvestigation() {
    try {
      setNotice('');
      $('hold-run').disabled = true;
      var payload = JSON.parse(JSON.stringify(HOLD_SAMPLE));
      payload.suspect.stage = $('hold-stage').value || payload.suspect.stage;
      payload.suspect.material_batch = $('hold-batch').value || payload.suspect.material_batch;
      await request('/api/holds/investigations', { method: 'POST', body: JSON.stringify(payload) });
      await loadHolds();
    } catch (error) { setNotice(error.message); }
    finally { $('hold-run').disabled = false; }
  }
  async function boot() {
    try {
      var catalog = await request('/api/catalog');
      state.kind = catalog.chart;
      state.resultColumns = catalog.result_columns;
      state.inputColumns = catalog.columns;
      stageButtons(catalog.stages.slice(0, 5));
      document.querySelector('.rail-note').textContent = catalog.code + ' · ' + catalog.stages[6].name;
      await loadStage('intake');
    } catch (error) { setNotice(error.message); }
    $('run').addEventListener('click', runBatch);
    $('sign').addEventListener('click', function () { review('APPROVED'); });
    $('hold').addEventListener('click', function () { review('HELD'); });
    $('hold-run').addEventListener('click', runHoldInvestigation);
    loadHolds();
    $('profile').addEventListener('change', function () {
      state.run = null; state.approved = false;
      $('sign').disabled = true; $('hold').disabled = true; $('download').hidden = true;
      $('run-status').textContent = '未执行批次'; $('revision').textContent = 'rev 0';
      loadStage('intake');
    });
  }
  document.addEventListener('DOMContentLoaded', boot);
})();
