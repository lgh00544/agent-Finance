/* ===== 系统治理交互原型 ===== */
'use strict';

/* ---------- 图标 ---------- */
const ICONS = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9 21v-6h6v6"/>',
  chart: '<path d="M3 3v18h18"/><path d="m7 14 4-4 3 3 5-6"/>',
  shield: '<path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3Z"/><path d="m9 12 2 2 4-4"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5 5-2Z"/>',
  news: '<path d="M4 4h13v16H4z"/><path d="M17 8h3v10a2 2 0 0 1-2 2h-1"/><path d="M7 8h7M7 12h7M7 16h4"/>',
  fire: '<path d="M12 3s5 4 5 9a5 5 0 0 1-10 0c0-2 1-3 1-3s0 2 2 2c2 0 2-3 2-8Z"/>',
  star: '<path d="m12 3 2.7 5.5 6 .9-4.4 4.3 1 6-5.3-2.8-5.3 2.8 1-6L3.3 9.4l6-.9L12 3Z"/>',
  plan: '<path d="M4 5h16v14H4z"/><path d="M8 3v4M16 3v4M4 10h16"/><path d="m9 15 2 2 4-4"/>',
  chat: '<path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8Z"/><path d="M8 11h8M8 15h5"/>',
  review: '<path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h8M8 17h5"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h14v18H6a2 2 0 0 0-2 2V5Z"/><path d="M6 3v18"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  undo: '<path d="M9 7 4 12l5 5"/><path d="M4 12h10a6 6 0 0 1 6 6v1"/>',
  rotate: '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/>',
  arrow: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  download: '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M4 21h16"/>',
  upload: '<path d="M12 21V9"/><path d="m7 14 5-5 5 5"/><path d="M4 3h16"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9"/><path d="m17 6 2 2M14 9l2 2"/>',
  alert: '<path d="M12 3 2 21h20L12 3Z"/><path d="M12 9v5M12 18h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  filter: '<path d="M3 5h18l-7 8v6l-4 2v-8L3 5Z"/>',
  sliders: '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="8" cy="18" r="2"/>',
  map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Z"/><path d="M9 4v14M15 6v14"/>',
  external: '<path d="M14 4h6v6"/><path d="M20 4 10 14"/><path d="M18 13v6H5V6h6"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  agent: '<rect x="4" y="7" width="16" height="12" rx="3"/><path d="M12 3v4M9 13h.01M15 13h.01M9 17h6"/>',
  workflow: '<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/><path d="M9 6h6a3 3 0 0 1 3 3v6"/>',
  tool: '<path d="m14 7 3-3 3 3-3 3"/><path d="m17 10-8 8-4 1 1-4 8-8"/>',
  link: '<path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"/>',
  ban: '<circle cx="12" cy="12" r="9"/><path d="m6 6 12 12"/>',
  caretUp: '<path d="m6 14 6-6 6 6"/>',
  caretDown: '<path d="m6 10 6 6 6-6"/>',
  minus: '<path d="M5 12h14"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>'
};

function icon(name, cls) {
  const path = ICONS[name] || ICONS.info;
  return '<span class="icon ' + (cls || '') + '"><svg viewBox="0 0 24 24" aria-hidden="true">' + path + '</svg></span>';
}

function hydrateIcons(root) {
  (root || document).querySelectorAll('[data-icon]').forEach((el) => {
    if (el.dataset.hydrated) return;
    el.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + (ICONS[el.dataset.icon] || ICONS.info) + '</svg>';
    el.dataset.hydrated = '1';
  });
}

/* ---------- 元数据 ---------- */
const AGENT_LABELS = {
  discover: '候选发现', score: '个股评分', position: '建仓规划',
  monitor: '持仓监控', sell: '卖出建议', review: '交易复盘', market_intel: '市场研判'
};
const RULE_TYPE = {
  hard: { label: '硬规则', cls: 'red' },
  soft: { label: '软性', cls: 'gold' },
  profile: { label: '偏好', cls: 'blue' }
};
const RULE_STATUS = {
  pending: { label: '待处理', cls: 'gold' },
  active: { label: '生效中', cls: 'green' },
  rolled_back: { label: '已回滚', cls: 'mute' },
  rejected: { label: '已驳回', cls: 'red' }
};
const AUDIT = {
  pending: { label: '待 AI 审', cls: 'gold' },
  auditing: { label: 'AI 审中', cls: 'blue' },
  pass: { label: 'AI 通过', cls: 'green' },
  fail: { label: 'AI 驳回', cls: 'red' }
};

const RULE_SEED = [
  {
    id: 'RC-1051', name: '候选池最低成交额', agent: 'discover', type: 'hard',
    status: 'pending', audit: 'pass', round: 2, confidence: 0.88,
    current: '3 亿元', suggested: '5 亿元',
    reason: '近 20 个交易日中，成交额低于 5 亿的候选标的 T+5 胜率仅 41%，滑点显著高于均值。',
    evidence: '复盘 #1033；流动性快照 2026-11-14；候选池 30 日命中率统计',
    problem: '低流动性标的在开盘 30 分钟内滑点扩大，实际成交价偏离监控价。',
    risk: '小盘题材股覆盖率下降约 7%，候选池数量预计减少 8-12 只。',
    createdAt: '2026-11-15 21:40', source: '复盘 #1033',
    auditLog: {
      verdict: 'pass', round: 2, confidence: 0.88,
      support: '成交额门槛上调与近 20 日流动性分布一致，未触发样本断层。',
      dissent: '小盘题材股覆盖率会下降约 7%。',
      boundary: '成交额 4.5-5.5 亿区间样本对阈值敏感。',
      evidenceRefs: ['复盘 #1033', '流动性快照 2026-11-14', '候选池 30 日统计'],
      model: 'audit-v2.3', at: '2026-11-16 09:12',
      reasoning: '{"verdict":"pass","checks":["sample_ok","coverage_drop"],"sample_size":1840,"risk_notes":["coverage_drop"]}'
    },
    timeline: [
      { time: '2026-11-15 21:40', title: '由复盘建议创建', body: '来源复盘 #1033，规则类建议自动进入审核流。', tone: 'info' },
      { time: '2026-11-16 08:55', title: 'AI 审核第 1 轮', body: '结论：需补充流动性样本，退回重审。', tone: 'warn' },
      { time: '2026-11-16 09:12', title: 'AI 审核第 2 轮通过', body: '置信度 0.88，建议进入人工审核。', tone: 'ok' }
    ]
  },
  {
    id: 'RC-1050', name: '单股最大仓位上限', agent: 'position', type: 'profile',
    status: 'pending', audit: 'fail', round: 2, confidence: 0.79,
    current: '15%', suggested: '12%',
    reason: '近 30 日高波动标的占比上升，希望降低单股集中度，减少组合回撤。',
    evidence: '复盘 #1028；组合波动率快照 2026-11-13',
    problem: '单一持仓在极端行情下贡献了 38% 的组合回撤。',
    risk: '与当前个人偏好 15% 冲突，可能降低强势股的收益贡献。',
    createdAt: '2026-11-15 20:05', source: '复盘 #1028',
    auditLog: {
      verdict: 'fail', round: 2, confidence: 0.79,
      support: '12% 更符合近期波动率，集中度风险下降。',
      dissent: '与现有偏好 15% 冲突，且对高确定性标的限制过强。',
      boundary: '账户总资产低于 50 万时差异不显著。',
      evidenceRefs: ['复盘 #1028', '组合波动率快照 2026-11-13'],
      model: 'audit-v2.3', at: '2026-11-16 08:47',
      reasoning: '{"verdict":"fail","reason":"conflicts_with_profile","confidence":0.79,"boundary":"asset_lt_500k"}'
    },
    timeline: [
      { time: '2026-11-15 20:05', title: '由复盘建议创建', body: '来源复盘 #1028。', tone: 'info' },
      { time: '2026-11-16 08:47', title: 'AI 审核驳回', body: '与个人偏好 15% 冲突，建议人工确认后再处理。', tone: 'err' }
    ]
  },
  {
    id: 'RC-1049', name: '卖出决策冷静期', agent: 'sell', type: 'soft',
    status: 'pending', audit: 'auditing', round: 1, confidence: null,
    current: '无', suggested: '10 分钟',
    reason: '触发卖出信号后立即执行的样本，事后 30 分钟反弹概率偏高。',
    evidence: '复盘 #1024；卖出后 30 分钟价格回补统计',
    problem: '情绪化卖出占比约 18%，需要短暂冷静期。',
    risk: '极端下跌时可能延迟止损，需保留人工强制卖出入口。',
    createdAt: '2026-11-14 22:18', source: '复盘 #1024',
    auditLog: null,
    timeline: [
      { time: '2026-11-14 22:18', title: '由复盘建议创建', body: '来源复盘 #1024，进入 AI 审核队列。', tone: 'info' },
      { time: '2026-11-16 09:30', title: 'AI 审核中', body: '第 1 轮审核进行中，预计 1-2 分钟。', tone: 'warn' }
    ]
  },
  {
    id: 'RC-1042', name: '移动止盈回撤阈值', agent: 'monitor', type: 'hard',
    status: 'active', audit: 'pass', round: 3, confidence: 0.91,
    current: '5%', suggested: '5%',
    reason: '近 30 个交易日移动止盈触发后回撤中位数 5.8%，将阈值收到 5%。',
    evidence: '复盘 #1042；移动止盈触发样本 46 笔',
    problem: '回撤阈值 6% 导致部分利润回吐。',
    risk: '可能提前止盈，降低单笔收益。',
    createdAt: '2026-11-10 19:35', source: '复盘 #1042',
    auditLog: {
      verdict: 'pass', round: 3, confidence: 0.91,
      support: '样本量与回撤分布支持 5% 阈值。',
      dissent: '强趋势行情下可能过早离场。',
      boundary: '单边上涨且波动率低于 15% 时差异明显。',
      evidenceRefs: ['复盘 #1042', '46 笔触发样本'],
      model: 'audit-v2.3', at: '2026-11-11 09:20',
      reasoning: '{"verdict":"pass","confidence":0.91,"round":3,"sample":46}'
    },
    timeline: [
      { time: '2026-11-10 19:35', title: '由复盘建议创建', body: '来源复盘 #1042。', tone: 'info' },
      { time: '2026-11-11 09:20', title: 'AI 审核通过', body: '置信度 0.91。', tone: 'ok' },
      { time: '2026-11-11 10:05', title: '人工采纳并生效', body: '规则版本写入 rule_change，全部 Agent 已携带。', tone: 'ok' }
    ]
  },
  {
    id: 'RC-1038', name: '新闻情绪权重', agent: 'market_intel', type: 'soft',
    status: 'pending', audit: 'auditing', round: 1, confidence: null,
    current: '0.15', suggested: '0.22',
    reason: '消息面驱动的板块行情中，情绪权重的解释力上升。',
    evidence: '行业消息雷达 30 日命中统计',
    problem: '情绪权重偏低，导致消息面异动在研判中滞后。',
    risk: '情绪噪声可能放大短期误判。',
    createdAt: '2026-11-14 16:20', source: '行业消息雷达',
    auditLog: null,
    timeline: [
      { time: '2026-11-14 16:20', title: '由消息雷达建议创建', body: '进入 AI 审核队列。', tone: 'info' },
      { time: '2026-11-16 09:31', title: 'AI 审核中', body: '第 1 轮审核进行中。', tone: 'warn' }
    ]
  },
  {
    id: 'RC-1031', name: '追高容忍度', agent: 'score', type: 'profile',
    status: 'active', audit: 'pass', round: 2, confidence: 0.84,
    current: '2.5%', suggested: '2.5%',
    reason: '开盘高开超过 2.5% 的标的日内回落概率偏高。',
    evidence: '评分样本 60 日回测',
    problem: '追高买入的回撤概率高于均值。',
    risk: '强势首板可能被排除。',
    createdAt: '2026-11-05 18:10', source: '复盘 #0991',
    auditLog: {
      verdict: 'pass', round: 2, confidence: 0.84,
      support: '样本支持 2.5% 阈值。',
      dissent: '强势首板可能被排除。',
      boundary: '涨停开盘样本不适用。',
      evidenceRefs: ['评分样本 60 日回测'],
      model: 'audit-v2.3', at: '2026-11-06 09:05',
      reasoning: '{"verdict":"pass","confidence":0.84}'
    },
    timeline: [
      { time: '2026-11-05 18:10', title: '由复盘建议创建', body: '来源复盘 #0991。', tone: 'info' },
      { time: '2026-11-06 09:05', title: 'AI 审核通过', body: '置信度 0.84。', tone: 'ok' },
      { time: '2026-11-06 09:40', title: '人工采纳并生效', body: '写入 rule_change。', tone: 'ok' }
    ]
  },
  {
    id: 'RC-1027', name: '复盘样本最小天数', agent: 'review', type: 'soft',
    status: 'rejected', audit: 'fail', round: 2, confidence: 0.72,
    current: '5 天', suggested: '10 天',
    reason: '希望延长复盘观察窗口，减少短期噪声。',
    evidence: '复盘 #0987',
    problem: '短期样本波动大，结论不稳定。',
    risk: '观察窗口过长，反馈闭环变慢。',
    createdAt: '2026-11-02 17:20', source: '复盘 #0987',
    auditLog: {
      verdict: 'fail', round: 2, confidence: 0.72,
      support: '更长窗口确实降低噪声。',
      dissent: '反馈闭环变慢，影响迭代速度。',
      boundary: '高频交易策略不适用。',
      evidenceRefs: ['复盘 #0987'],
      model: 'audit-v2.2', at: '2026-11-03 09:10',
      reasoning: '{"verdict":"fail","reason":"feedback_loop_slow"}'
    },
    timeline: [
      { time: '2026-11-02 17:20', title: '由复盘建议创建', body: '来源复盘 #0987。', tone: 'info' },
      { time: '2026-11-03 09:10', title: 'AI 审核驳回', body: '反馈闭环变慢，风险大于收益。', tone: 'err' },
      { time: '2026-11-03 10:00', title: '人工驳回', body: '原因：保留 5 天窗口，维持现有迭代速度。', tone: 'err' }
    ]
  },
  {
    id: 'RC-1019', name: '游资席位权重', agent: 'market_intel', type: 'soft',
    status: 'rolled_back', audit: 'pass', round: 2, confidence: 0.81,
    current: '0.30（已恢复）', suggested: '0.20',
    reason: '回测显示游资席位权重下调后，板块研判准确率提升。',
    evidence: '游资追踪 20 日回测',
    problem: '游资信号权重偏高，造成板块误判。',
    risk: '样本量不足，结论可能不稳定。',
    createdAt: '2026-10-28 19:00', source: '复盘 #0955',
    auditLog: {
      verdict: 'pass', round: 2, confidence: 0.81,
      support: '回测准确率提升 4.2%。',
      dissent: '样本量仅 38 个交易日。',
      boundary: '题材切换频繁时效果差异大。',
      evidenceRefs: ['游资追踪 20 日回测'],
      model: 'audit-v2.2', at: '2026-10-29 09:00',
      reasoning: '{"verdict":"pass","confidence":0.81,"sample_days":38}'
    },
    timeline: [
      { time: '2026-10-28 19:00', title: '由复盘建议创建', body: '来源复盘 #0955。', tone: 'info' },
      { time: '2026-10-29 09:00', title: 'AI 审核通过', body: '置信度 0.81。', tone: 'ok' },
      { time: '2026-10-29 10:20', title: '人工采纳并生效', body: '写入 rule_change，权重 0.30 → 0.20。', tone: 'ok' },
      { time: '2026-11-15 22:05', title: '人工回滚', body: '原因：回测样本不足，恢复原权重 0.30。', tone: 'warn' }
    ]
  }
];

const FACTOR_PROPOSALS = [
  {
    fid: 'FACT-MOM-20D', name: '动量 20 日', category: '动量',
    icHistory: [0.011, 0.006, -0.004, 0.009, -0.002, 0.007],
    months: '2026-06 → 2026-11',
    reason: '连续 3 个月 |IC| < 0.02，样本充足（n=1820），但预测力接近于零。',
    source: '自动回测', at: '2026-11-16 10:20'
  },
  {
    fid: 'FACT-TURN-SURGE', name: '换手突增', category: '流动性',
    icHistory: [0.018, 0.012, 0.009, -0.003, 0.004, 0.006],
    months: '2026-06 → 2026-11',
    reason: '连续 3 个月 |IC| < 0.02；近期与涨停样本高度重叠，独立信息量下降。',
    source: '自动回测', at: '2026-11-16 10:20'
  }
];

const FACTOR_HISTORY = [
  { id: 'IC-2411', fid: 'FACT-MOM-20D', name: '动量 20 日', category: '动量', period: '2026-11', ic: 0.007, ir: 0.18, hit: 0.51, sample: 1820, rank: 7, status: 'deprecated_candidate' },
  { id: 'IC-2410', fid: 'FACT-TURN-SURGE', name: '换手突增', category: '流动性', period: '2026-11', ic: 0.006, ir: 0.15, hit: 0.49, sample: 1744, rank: 9, status: 'deprecated_candidate' },
  { id: 'IC-2409', fid: 'FACT-VOL-60D', name: '波动率 60 日', category: '风险', period: '2026-11', ic: -0.031, ir: -0.42, hit: 0.56, sample: 1820, rank: 2, status: 'active' },
  { id: 'IC-2408', fid: 'FACT-VALUE', name: '估值分位', category: '价值', period: '2026-11', ic: 0.026, ir: 0.33, hit: 0.54, sample: 1796, rank: 3, status: 'active' },
  { id: 'IC-2407', fid: 'FACT-QUALITY', name: '质量因子', category: '质量', period: '2026-11', ic: 0.019, ir: 0.21, hit: 0.52, sample: 1810, rank: 5, status: 'active' },
  { id: 'IC-2406', fid: 'FACT-REV-5D', name: '短期反转 5 日', category: '反转', period: '2026-11', ic: -0.024, ir: -0.29, hit: 0.55, sample: 96, rank: 4, status: 'active' },
  { id: 'IC-2405', fid: 'FACT-FUND-FLOW', name: '主力资金流', category: '资金', period: '2026-11', ic: 0.034, ir: 0.46, hit: 0.58, sample: 1820, rank: 1, status: 'active' },
  { id: 'IC-2404', fid: 'FACT-NEWS-SENT', name: '新闻情绪', category: '情绪', period: '2026-11', ic: 0.014, ir: 0.12, hit: 0.5, sample: 88, rank: 8, status: 'active' },
  { id: 'IC-2403', fid: 'FACT-INDUSTRY-ROT', name: '行业轮动', category: '行业', period: '2026-11', ic: 0.022, ir: 0.27, hit: 0.53, sample: 1802, rank: 4, status: 'active' },
  { id: 'IC-2402', fid: 'FACT-SIZE', name: '市值因子', category: '风格', period: '2026-11', ic: -0.017, ir: -0.16, hit: 0.48, sample: 1820, rank: 6, status: 'active' }
];

const HEALTH_MODULES = [
  {
    module: 'rule_change_audit', name: '规则变更审计', status: 'attention',
    counts: '待处理 2 · AI 失败 1 · 生效规则 6',
    reason: '2 条建议待人工审核，1 条 AI 审核失败需重跑。',
    action: '先处理人工待审，再重跑 AI 失败项；不自动放行。',
    link: '#/system/rules', linkLabel: '去处理'
  },
  {
    module: 'knowledge', name: '知识库', status: 'healthy',
    counts: '总条目 420 · 待审 0',
    reason: '条目结构与更新时间均正常。',
    action: '保持只读，无需处理。',
    link: '#/knowledge', linkLabel: '打开'
  },
  {
    module: 'shadow', name: '影子记录 / 失败重放', status: 'attention',
    counts: '待补算 142 · 失败 7',
    reason: '存在未补算的 T+N 记录和失败重放。',
    action: '先补算或回放失败记录，再纳入正式治理。',
    link: '#/reviews', linkLabel: '打开验证'
  },
  {
    module: 'experience_memory', name: '经验沉淀', status: 'attention',
    counts: '建议总数 35 · AI 待审 3 · 人工待审 2',
    reason: '高影响经验建议等待人工审核。',
    action: '按影响面排序审核，避免批量放行。',
    link: '#/experience', linkLabel: '打开'
  },
  {
    module: 'collaboration', name: '协作矩阵', status: 'healthy',
    counts: '明确允许 21 · 默认禁止 1320 · 运行时拒绝 4',
    reason: '白名单与默认禁止边界清晰。',
    action: '抽查 4 条运行时拒绝记录即可。',
    link: '#/system/capability', linkLabel: '查看矩阵'
  },
  {
    module: 'database_migration', name: '数据库迁移', status: 'unknown',
    counts: '无迁移快照',
    reason: '当前没有可确认的迁移快照。',
    action: '重启或重新初始化后复核；保留 unknown 标识。',
    link: '', linkLabel: ''
  },
  {
    module: 'registration_integrity', name: '注册完整性', status: 'healthy',
    counts: '注册条目 17 · 活跃 17',
    reason: '无缺失注册，无漂移。',
    action: '保持只读。',
    link: '#/system/capability', linkLabel: '查看能力'
  }
];

const GOV_EVENTS = [
  { time: '2026-11-16 10:20', title: '因子失效建议进入待决策', body: 'FACT-MOM-20D、FACT-TURN-SURGE 连续 3 个月 |IC| < 0.02。', tone: 'warn' },
  { time: '2026-11-16 09:12', title: 'AI 审核通过：候选池最低成交额', body: '置信度 0.88，等待人工审核。', tone: 'ok' },
  { time: '2026-11-16 08:47', title: 'AI 审核驳回：单股最大仓位上限', body: '与个人偏好 15% 冲突，需人工确认。', tone: 'err' },
  { time: '2026-11-15 22:05', title: '人工回滚：游资席位权重', body: '原因：回测样本不足，恢复原权重 0.30。', tone: 'mute' },
  { time: '2026-11-15 21:40', title: '新建议：候选池最低成交额', body: '来源复盘 #1033，自动进入审核流。', tone: 'info' },
  { time: '2026-11-14 18:30', title: '个人偏好保存 v12', body: '单股最大仓位 15%，默认止损 7%。', tone: 'info' }
];

const AGENTS = [
  { id: 'discover', name: '候选发现', responsibility: '每日候选挖掘与初筛，输出候选池。', type: '研究决策', authority: '提议权限', scope: '市场范围', inputs: ['交易日', '市场快照'], optional: ['板块偏好'], outputs: ['候选池', '初筛理由'], canRef: [], canCall: ['score'], cannot: ['直接建仓', '修改规则'], gate: false },
  { id: 'score', name: '个股评分', responsibility: '六因子评分与综合评级，给出 A/B/C 分级。', type: '研究决策', authority: '提议权限', scope: '市场范围', inputs: ['股票代码', '交易日'], optional: ['因子权重'], outputs: ['评分报告', '风险计数'], canRef: ['discover'], canCall: [], cannot: ['修改因子权重', '自动采纳'], gate: false },
  { id: 'position', name: '建仓规划', responsibility: '根据评分与个人偏好生成建仓方案。', type: '入口编排', authority: '提议权限', scope: '指定 Agent', inputs: ['股票代码', '评分报告'], optional: ['个人偏好'], outputs: ['建仓方案', '分档买入'], canRef: ['score'], canCall: [], cannot: ['自动下单', '修改偏好'], gate: true },
  { id: 'monitor', name: '持仓监控', responsibility: '止盈止损、红线预警与持仓风险监控。', type: '研究决策', authority: '咨询权限', scope: '市场范围', inputs: ['持仓明细', '行情快照'], optional: ['止盈计划'], outputs: ['监控告警', '风险提示'], canRef: ['position'], canCall: ['sell'], cannot: ['执行交易', '清仓'], gate: true },
  { id: 'sell', name: '卖出建议', responsibility: '结合持仓与市场状态给出卖出建议。', type: '研究决策', authority: '咨询权限', scope: '指定 Agent', inputs: ['持仓明细', '行情快照'], optional: ['复盘经验'], outputs: ['卖出建议', '理由链'], canRef: ['monitor'], canCall: [], cannot: ['执行卖出', '修改规则'], gate: true },
  { id: 'review', name: '交易复盘', responsibility: '盘后复盘、归因分析与规则建议生成。', type: '经验治理', authority: '提议权限', scope: '市场范围', inputs: ['交易记录', '行情快照'], optional: ['历史经验'], outputs: ['复盘结论', '规则建议'], canRef: [], canCall: [], cannot: ['自动采纳建议', '修改规则'], gate: true },
  { id: 'track_verify', name: '选股验证', responsibility: 'T+3/5/10 收益验证与胜率统计。', type: '研究决策', authority: '只读数据', scope: '市场范围', inputs: ['选股日期', '股票代码'], optional: [], outputs: ['验证结果', '胜率统计'], canRef: ['discover'], canCall: [], cannot: ['修改候选池', '执行交易'], gate: false },
  { id: 'market_intel', name: '市场研判', responsibility: '市场结构、板块前瞻与消息面研判。', type: '研究决策', authority: '咨询权限', scope: '市场范围', inputs: ['行情快照', '消息数据'], optional: ['历史规律'], outputs: ['研判结论', '板块前瞻'], canRef: [], canCall: [], cannot: ['直接选股', '执行交易'], gate: false }
];

const WORKFLOWS = [
  { id: 'discover_daily', name: '每日候选挖掘', intent: '今天有什么机会', steps: '拉取行情 → 初筛 → 生成候选池', inputs: '交易日', gate: '仅分析 / 查询', final: '候选发现' },
  { id: 'score_batch', name: '批量评分', intent: '给候选打分', steps: '读取候选 → 六因子评分 → 输出评级', inputs: '交易日', gate: '仅分析 / 查询', final: '个股评分' },
  { id: 'position_plan', name: '生成建仓方案', intent: '这只股票怎么买', steps: '评分 → 偏好约束 → 分档买入', inputs: '股票代码', gate: '需审核 · 需人工确认', final: '建仓规划' },
  { id: 'monitor_sweep', name: '持仓巡检', intent: '持仓要不要处理', steps: '拉取持仓 → 止盈止损 → 告警', inputs: '持仓明细', gate: '需审核 · 需人工确认', final: '持仓监控' },
  { id: 'sell_decision', name: '卖出决策', intent: '要不要卖', steps: '持仓 → 风险与信号 → 卖出建议', inputs: '股票代码', gate: '需审核 · 需人工确认', final: '卖出建议' },
  { id: 'review_daily', name: '盘后复盘', intent: '今天做得怎么样', steps: '交易记录 → 归因 → 规则建议', inputs: '交易日', gate: '需审核 · 需人工确认', final: '交易复盘' },
  { id: 'track_verify', name: '选股效果验证', intent: '选股准不准', steps: '候选 → T+N 收益 → 胜率', inputs: '选股日期', gate: '仅分析 / 查询', final: '选股验证' },
  { id: 'market_intel', name: '市场研判', intent: '今天市场怎么样', steps: '行情 → 板块结构 → 前瞻', inputs: '交易日', gate: '仅分析 / 查询', final: '市场研判' },
  { id: 'rule_audit', name: '规则建议审核', intent: '这条规则要不要采纳', steps: '建议 → AI 审核 → 人工确认', inputs: '建议 ID', gate: '需审核 · 需人工确认', final: '经验治理' }
];

const TOOLS = [
  { id: 'get_quote', name: '实时行情快照', owner: '行情服务', desc: '返回最新价格、涨跌幅与成交量。', usedBy: 'discover / monitor / sell' },
  { id: 'get_daily_kline', name: '日 K 线', owner: '行情服务', desc: '返回指定标的的日线序列。', usedBy: 'score / review' },
  { id: 'get_news', name: '新闻公告', owner: '消息服务', desc: '返回个股与行业新闻、公告。', usedBy: 'market_intel' },
  { id: 'get_financial', name: '财务指标', owner: '财务服务', desc: '返回估值与质量因子所需的财务数据。', usedBy: 'score' },
  { id: 'get_fund_flow', name: '资金流向', owner: '资金服务', desc: '返回主力资金与北向资金流向。', usedBy: 'score / market_intel' },
  { id: 'search_knowledge', name: '知识库检索', owner: '知识库', desc: '在交易知识库中做只读检索。', usedBy: 'review / agent_chat' },
  { id: 'get_sector_regime', name: '板块状态', owner: '板块服务', desc: '返回板块强弱与轮动状态。', usedBy: 'market_intel' },
  { id: 'get_factor_calibration', name: '因子校准', owner: '因子服务', desc: '返回当前因子权重与校准结果。', usedBy: 'score' },
  { id: 'get_distribution_phase', name: '派发阶段', owner: '行情结构', desc: '返回标的所处的派发阶段判断。', usedBy: 'market_intel / monitor' },
  { id: 'get_capital_view', name: '资本视图', owner: '资金服务', desc: '返回资金结构视图。', usedBy: 'market_intel' },
  { id: 'get_position_risk', name: '持仓风险', owner: '风控服务', desc: '返回单股与组合风险指标。', usedBy: 'monitor / sell' },
  { id: 'get_market_breadth', name: '市场宽度', owner: '行情服务', desc: '返回涨跌家数与市场宽度。', usedBy: 'market_intel' }
];

const COLLAB_RULES = [
  { requester: 'discover', target: 'score', relation: 'call', allowed: true, depth: 1, policy: '返回错误信息', audit: false, reason: '候选发现调用评分生成候选评分。' },
  { requester: 'monitor', target: 'sell', relation: 'call', allowed: true, depth: 1, policy: '返回错误信息', audit: true, reason: '持仓监控在触发风险时请求卖出建议。' },
  { requester: 'position', target: 'score', relation: 'reference', allowed: true, depth: 1, policy: 'deny_by_default', audit: false, reason: '建仓规划引用评分结果，不修改评分。' },
  { requester: 'sell', target: 'monitor', relation: 'reference', allowed: true, depth: 1, policy: 'deny_by_default', audit: true, reason: '卖出建议引用持仓监控的风险快照。' },
  { requester: 'review', target: 'discover', relation: 'propose_change', allowed: true, depth: 1, policy: 'deny_by_default', audit: true, reason: '复盘可提出候选规则变更，但不直接修改。' },
  { requester: 'market_intel', target: 'discover', relation: 'propose_change', allowed: true, depth: 1, policy: 'deny_by_default', audit: true, reason: '研判可提出候选调整建议，需走审核。' }
];

/* ---------- 状态 ---------- */
const state = {
  route: '',
  ruleBucket: 'todo',
  ruleQuery: '',
  ruleAgent: '',
  ruleType: '',
  selectedRuleId: 'RC-1051',
  ruleDetailTab: 'suggestion',
  ruleSort: 'new',
  ruleChecked: [],
  batchAction: null,
  pendingAction: null,
  rules: clone(RULE_SEED),
  factors: clone(FACTOR_PROPOSALS),
  factorHistory: clone(FACTOR_HISTORY),
  factorCategory: '',
  factorQuery: '',
  factorConfirm: null,
  candId: '603501',
  candQuery: '',
  candTier: '',
  candTab: 'conclusion',
  candNewsFilter: '',
  candNewsLinked: true,
  candNewsOpen: false,
  candAddOpen: false,
  candMode: 'today',
  candBatch: '2026-11-12',
  rvBoard: 'list',
  rvId: 1044,
  rvTab: 'result',
  rvFilter: '',
  rvBatch: '',
  rvConfirm: null,
  rvRejectIn: null,
  rvTrackDate: '2026-11-12',
  sgsId: 3024,
  sgsTab: 'content',
  sgsFilter: '',
  sgsAuditFilter: '',
  sgsConfirm: null,
  sgsRejectIn: null,
  sgsQuickConfirm: null,
  fcFilter: '',
  expId: 'EXP-0021',
  expTab: 'review',
  expTab2: 'content',
  expStage: '',
  expConfirm: null,
  expRejectIn: null,
  expQuickConfirm: null,
  paletteIndex: 0,
  collabResult: null
};

function clone(value) { return JSON.parse(JSON.stringify(value)); }

/* ---------- 工具 ---------- */
function esc(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

/* 搜索命中高亮 */
function highlight(text, query) {
  const t = esc(text);
  const q = esc(query).trim();
  if (!q) return t;
  const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
  return t.replace(re, (m) => '<mark>' + m + '</mark>');
}

/* 前端直接生成文件下载（导出留痕用） */
function download(filename, text, mime) {
  const blob = new Blob([text], { type: mime || 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
function $(sel, root) { return (root || document).querySelector(sel); }
function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }
function tag(text, cls) { return '<span class="tag ' + (cls || '') + '">' + esc(text) + '</span>'; }
function agentLabel(id) { return AGENT_LABELS[id] || id || '—'; }
function ruleTypeTag(type) { const m = RULE_TYPE[type] || { label: type, cls: '' }; return tag(m.label, m.cls); }
function ruleStatusTag(status) { const m = RULE_STATUS[status] || { label: status, cls: '' }; return tag(m.label, m.cls); }
function auditTag(audit) { const m = AUDIT[audit] || { label: audit, cls: '' }; return tag(m.label, m.cls); }

/* 「2026-11-16 15:20」→「2 小时前」，让人一眼知道新旧 */
const NOW_REF = new Date('2026-11-16T17:30:00');
function relTime(text) {
  const raw = String(text || '').replace('T', ' ');
  if (!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(raw)) return raw;
  const then = new Date(raw.replace(' ', 'T'));
  const mins = Math.round((NOW_REF - then) / 60000);
  if (isNaN(mins)) return raw;
  if (mins <= 1) return '刚刚';
  if (mins < 60) return mins + ' 分钟前';
  const hours = Math.round(mins / 60);
  if (hours < 24) return hours + ' 小时前';
  const days = Math.round(hours / 24);
  if (days < 30) return days + ' 天前';
  return raw.slice(0, 10);
}

/* 状态用一个点 + 一个词，替代四五个彩色标签 */
function ruleState(rule) {
  if (rule.status === 'pending') return rule.audit === 'auditing'
    ? '<span class="state run">AI 审核中</span>'
    : rule.audit === 'fail'
      ? '<span class="state bad">AI 审核未通过</span>'
      : '<span class="state todo">等你决定</span>';
  if (rule.status === 'active') return '<span class="state done">已生效</span>';
  if (rule.status === 'rejected') return '<span class="state off">已驳回</span>';
  if (rule.status === 'rolled_back') return '<span class="state off">已回滚</span>';
  return '<span class="state off">' + esc(rule.status) + '</span>';
}

/* 列表行右侧的状态胶囊：颜色只分四档，且同一行只出现一个 */
function rulePill(rule) {
  let cls = 'off';
  let label = rule.status;
  if (rule.status === 'pending') {
    if (rule.audit === 'auditing') { cls = 'run'; label = 'AI 审核中'; }
    else if (rule.audit === 'fail') { cls = 'todo'; label = 'AI 未通过'; }
    else { cls = 'todo'; label = '等你决定'; }
  } else if (rule.status === 'active') { cls = 'done'; label = '已生效'; }
  else if (rule.status === 'rejected') { cls = 'off'; label = '已驳回'; }
  else if (rule.status === 'rolled_back') { cls = 'off'; label = '已回滚'; }
  return '<span class="rr-pill ' + cls + '">' + esc(label) + '</span>';
}

/* 留痕动作由谁做出：AI / 人工 / 系统。后端记录里若有 actor 字段则以它为准 */
function actorChip(item) {
  const explicit = item && item.actor;
  const t = String((item && item.title) || '');
  const who = explicit || (/AI|审核|回测/.test(t) && !/人工|你/.test(t) ? 'ai'
    : /采纳|驳回|回滚|保存|导入|确认|下线|保留|触发/.test(t) ? 'human' : 'sys');
  const label = { ai: 'AI', human: '人工', sys: '系统' }[who] || '系统';
  return '<span class="actor ' + who + '">' + label + '</span>';
}

function toast(title, body, kind, action) {
  const root = $('#toast-root');
  const el = document.createElement('div');
  el.className = 'toast ' + (kind || '');
  el.innerHTML = '<div class="toast-title">' + esc(title) + '</div><div class="toast-body">' + esc(body || '') + '</div>';
  if (action && action.label) {
    const wrap = document.createElement('div');
    wrap.className = 'toast-act';
    const btn = document.createElement('button');
    btn.className = 'btn sm';
    btn.textContent = action.label;
    btn.addEventListener('click', () => { el.remove(); action.fn(); });
    wrap.appendChild(btn);
    el.appendChild(wrap);
  }
  root.appendChild(el);
  const life = action ? 6000 : 2900;
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .2s ease'; }, life);
  setTimeout(() => { el.remove(); }, life + 300);
}

function statusTag(text, status) {
  const map = {
    healthy: { label: '正常', cls: 'green' },
    attention: { label: '需关注', cls: 'gold' },
    error: { label: '错误', cls: 'red' },
    unknown: { label: '未知', cls: 'mute' }
  };
  const m = map[status] || map.unknown;
  return tag(text || m.label, m.cls);
}

function ruleBucketOf(rule) {
  if (rule.status === 'pending') {
    if (rule.audit === 'pending' || rule.audit === 'auditing') return 'auditing';
    return 'todo';
  }
  if (rule.status === 'active') return 'active';
  if (rule.status === 'rejected') return 'rejected';
  if (rule.status === 'rolled_back') return 'rolled_back';
  return 'all';
}

function bucketCounts() {
  const counts = { todo: 0, auditing: 0, active: 0, rejected: 0, rolled_back: 0, all: state.rules.length };
  state.rules.forEach((r) => { const b = ruleBucketOf(r); if (counts[b] != null) counts[b] += 1; });
  return counts;
}

function filteredRules() {
  const q = state.ruleQuery.trim().toLowerCase();
  const list = state.rules
    .filter((r) => state.ruleBucket === 'all' || ruleBucketOf(r) === state.ruleBucket)
    .filter((r) => !state.ruleAgent || r.agent === state.ruleAgent)
    .filter((r) => !state.ruleType || r.type === state.ruleType)
    .filter((r) => !q || (r.name + ' ' + r.reason + ' ' + r.id).toLowerCase().includes(q));
  if (state.ruleSort === 'status') {
    const weight = { pending_pass: 0, pending_fail: 1, pending_auditing: 2, active: 3, rejected: 4, rolled_back: 5 };
    list.sort((a, b) => (weight[bucketKey(a)] ?? 9) - (weight[bucketKey(b)] ?? 9) ||
      String(b.createdAt).localeCompare(String(a.createdAt)));
  } else {
    list.sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
  }
  return list;
}
function bucketKey(rule) {
  const b = ruleBucketOf(rule);
  if (b !== 'todo') return b;
  return rule.audit === 'auditing' ? 'pending_auditing' : rule.audit === 'fail' ? 'pending_fail' : 'pending_pass';
}

/* ---------- 导航 ---------- */
const NAV = [
  {
    group: '今日', items: [
      { path: '#/overview', label: '工作台总览', icon: 'home' },
      { path: '#/candidates', label: '每日候选池', icon: 'chart' },
      { path: '#/holdings', label: '持仓监控', icon: 'shield' },
      { path: '#/alerts', label: '告警日志', icon: 'bell' }
    ]
  },
  {
    group: '研究', items: [
      { path: '#/market-intel', label: '市场研判', icon: 'compass' },
      { path: '#/news-sector', label: '行业消息雷达', icon: 'news' },
      { path: '#/hot-money', label: '游资追踪', icon: 'fire' },
      { path: '#/scores', label: '评分报告', icon: 'star' }
    ]
  },
  {
    group: '计划', items: [
      { path: '#/plans', label: '建仓计划', icon: 'plan' },
      { path: '#/agent-chat', label: 'Agent 对话', icon: 'chat' }
    ]
  },
  {
    group: '复盘', items: [
      { path: '#/reviews', label: '交易复盘', icon: 'review' },
      { path: '#/experience', label: '经验沉淀', icon: 'layers' },
      { path: '#/knowledge', label: '交易知识库', icon: 'book' }
    ]
  },
  {
    group: '系统', items: [
      { path: '#/system/overview', label: '系统与治理', icon: 'shield', badge: true }
    ]
  }
];

const GOV_TABS = [
  { key: 'overview', label: '治理总览', path: '#/system/overview' },
  { key: 'rules', label: '规则审计', path: '#/system/rules' },
  { key: 'factors', label: '因子回测', path: '#/system/factors' },
  { key: 'capability', label: '能力地图', path: '#/system/capability' }
];

const PLACEHOLDERS = {
  '#/holdings': {
    title: '持仓监控', desc: '下一批设计：卡片/列表 + 详情抽屉，操作入口固定在首行。',
    scope: ['组合概览与告警优先', '详情抽屉：持仓操作、流水、止盈计划、卖出决策', '加仓/减仓/清仓就地完成，不跳页', '卖出决策结果回写到持仓时间线']
  },
  '#/alerts': { title: '告警日志', desc: '下一批设计：按严重度分组，支持一键进入对应持仓或规则。', scope: ['严重度分组与已读状态', '告警 → 持仓 / 规则 / 复盘 的深链', '保留原始 payload 折叠查看'] },
  '#/market-intel': { title: '市场研判', desc: '下一批设计：结论先行，12 张卡片按「主线 → 验证 → 风险」重组。', scope: ['首屏只留主线结论与三个关键指标', '板块与个股验证按需展开', '历史准确率做成趋势而非孤立卡片'] },
  '#/news-sector': { title: '行业消息雷达', desc: '下一批设计：按影响面排序，消息与板块联动。', scope: ['高影响消息置顶', '消息详情抽屉 + 关联板块', '已读/已处理状态'] },
  '#/hot-money': { title: '游资追踪', desc: '下一批设计：席位与个股联动，减少多表切换。', scope: ['席位列表 + 个股详情抽屉', '异常席位优先', '与市场研判互链'] },
  '#/scores': { title: '评分报告', desc: '下一批设计：评分表 + 详情抽屉，采纳状态更清晰。', scope: ['A/B/C 分级筛选', '六因子解释与风险计数', '一键去建仓计划'] },
  '#/plans': { title: '建仓计划', desc: '下一批设计：从候选池承接上下文，方案详情分区 Tab 化。', scope: ['候选来源可追溯', '分档买入、止盈止损、依据分 Tab', '采纳/放弃就地留痕'] },
  '#/agent-chat': { title: 'Agent 对话', desc: '下一批设计：保留看板化对话，接入治理留痕。', scope: ['任务型对话与普通问答分流', '任务状态与结果卡片', '留痕与治理深链'] },
  '#/knowledge': { title: '交易知识库', desc: '下一批设计：检索优先，条目审核轻量化。', scope: ['全局检索', '条目详情与来源', '审核状态'] }
};

/* ---------- 路由 ---------- */
function parseRoute() {
  const raw = location.hash || '#/system/overview';
  const qi = raw.indexOf('?');
  const path = qi < 0 ? raw : raw.slice(0, qi);
  state.route = path;
  if (path === '#/system/rules') {
    const params = new URLSearchParams(qi < 0 ? '' : raw.slice(qi + 1));
    const b = params.get('bucket');
    if (b && b in bucketCounts()) state.ruleBucket = b;
    const id = params.get('id');
    if (id && state.rules.some((r) => r.id === id)) state.selectedRuleId = id;
  }
  if (path === '#/candidates') {
    const params = new URLSearchParams(qi < 0 ? '' : raw.slice(qi + 1));
    const id = params.get('id');
    if (id && CANDIDATE_POOL.some((c) => c.stock_code === id)) { state.candId = id; state.candMode = 'today'; }
    const d = params.get('date');
    if (d && CAND_BATCHES.some((b) => b.date === d)) { state.candBatch = d; state.candMode = 'history'; }
    if (params.get('mode') === 'today') state.candMode = 'today';
  }
  if (path === '#/reviews') {
    const params = new URLSearchParams(qi < 0 ? '' : raw.slice(qi + 1));
    const d = params.get('date');
    if (d && CAND_BATCHES.some((b) => b.date === d)) { state.rvBatch = d; state.rvBoard = 'list'; }
    const rid = params.get('id');
    const rv = reviewById(rid);
    if (rv) { state.rvId = rv.id; state.rvBoard = 'list'; }
    const bd = params.get('board');
    if (bd && RV_BOARDS.some((b) => b[0] === bd)) state.rvBoard = bd;
    const sg = params.get('sgs');
    if (sg && SUG_ROWS.some((s) => String(s.id) === String(sg))) { state.sgsId = Number(sg); state.rvBoard = 'sug'; }
    const tk = params.get('track');
    if (tk && CAND_BATCHES.some((b) => b.date === tk)) { state.rvTrackDate = tk; state.rvBoard = 'track'; }
  }
  if (path === '#/experience') {
    const params = new URLSearchParams(qi < 0 ? '' : raw.slice(qi + 1));
    const ex = expById(params.get('id'));
    if (ex) { state.expId = ex.id; state.expTab = expBucketOf(ex); }
  }
  return path;
}

/* 把队列与选中规则写回 URL：刷新、转发链接都能还原现场 */
function syncRuleHash() {
  if (state.route !== '#/system/rules') return;
  const p = new URLSearchParams();
  p.set('bucket', state.ruleBucket);
  if (state.selectedRuleId) p.set('id', state.selectedRuleId);
  const next = '#/system/rules?' + p.toString();
  if (location.hash !== next) history.replaceState(null, '', next);
}

function govTabKey() {
  const route = state.route;
  if (!route.startsWith('#/system/')) return 'overview';
  return route.replace('#/system/', '') || 'overview';
}

function navLabelFor(path) {
  for (const g of NAV) {
    const hit = g.items.find((it) => it.path === path);
    if (hit) return { group: g.group, label: hit.label };
  }
  const tab = GOV_TABS.find((t) => t.path === path);
  if (tab) return { group: '系统', label: tab.label };
  return { group: '', label: '页面' };
}

function renderSidebar() {
  const counts = bucketCounts();
  const nav = $('#nav');
  nav.innerHTML = NAV.map((group) => (
    '<div class="nav-group">' +
      '<div class="nav-group-title">' + esc(group.group) + '</div>' +
      group.items.map((item) => {
        const active = state.route === item.path || (item.path === '#/system/overview' && state.route.startsWith('#/system/'));
        const badge = item.badge && counts.todo > 0 ? '<span class="nav-badge">' + counts.todo + '</span>' : '';
        return '<button class="nav-item ' + (active ? 'active' : '') + '" data-nav="' + item.path + '" title="' + esc(item.label) + '">' +
          icon(item.icon) + '<span class="nav-label">' + esc(item.label) + '</span>' + badge + '</button>';
      }).join('') +
    '</div>'
  )).join('');
}

function renderCrumb() {
  const hash = state.route;
  let html = '';
  if (hash.startsWith('#/system/')) {
    const tab = GOV_TABS.find((t) => t.path === hash) || GOV_TABS[0];
    html = '<span>A股决策 Agent</span><span class="crumb-sep">/</span><span class="crumb-mid">系统与治理</span><span class="crumb-sep crumb-mid">/</span><strong>' + esc(tab.label) + '</strong>';
  } else {
    const info = navLabelFor(hash);
    html = '<span>A股决策 Agent</span><span class="crumb-sep">/</span><span class="crumb-mid">' + esc(info.group) + '</span><span class="crumb-sep crumb-mid">/</span><strong>' + esc(info.label) + '</strong>';
  }
  $('#crumb').innerHTML = html;
}

/* ---------- 页面外壳 ---------- */
function governanceHeader(actionsHtml) {
  const counts = bucketCounts();
  const needYou = counts.todo + state.factors.length;
  const hour = NOW_REF.getHours();
  const hi = hour < 11 ? '早上好' : hour < 14 ? '中午好' : hour < 19 ? '下午好' : '晚上好';
  const chip = needYou > 0
    ? '<span class="greet-chip">' + icon('bell', 'sm') + '今天有 ' + needYou + ' 件事需要你确认</span>'
    : '<span class="greet-chip zero">' + icon('check', 'sm') + '该你决定的都处理完了</span>';
  return '<div class="page-head">' +
    '<div>' +
      '<div class="page-title">' + esc(hi) + '，这里是系统与治理</div>' +
      '<div class="greet-line">' + chip + '<span class="small muted">其余内容均为只读，不会改动线上策略。</span></div>' +
    '</div>' +
    '<div class="page-actions">' + (actionsHtml || '') + '</div>' +
  '</div>';
}

function governanceTabs(active) {
  const counts = bucketCounts();
  const factorCount = state.factors.length;
  const tabs = GOV_TABS.map((t) => {
    let extra = '';
    if (t.key === 'rules' && counts.todo > 0) extra = '<span class="tab-count">' + counts.todo + '</span>';
    if (t.key === 'factors' && factorCount > 0) extra = '<span class="tab-count">' + factorCount + '</span>';
    return '<button class="tab ' + (active === t.key ? 'active' : '') + '" data-nav="' + t.path + '">' + esc(t.label) + extra + '</button>';
  }).join('');
  return '<div class="tabs">' + tabs + '</div>';
}

function auditButton() {
  const n = state.rules.filter((r) => r.audit === 'pending' || r.audit === 'auditing').length;
  return '<button class="btn primary" data-action="audit-all" ' + (n ? '' : 'disabled') + '>' +
    icon('rotate', 'sm') + '增量 AI 审核' + (n ? '<span class="tab-count">' + n + '</span>' : '') + '</button>';
}

function renderGovernanceShell(activeKey, body) {
  let actions = '';
  if (activeKey === 'overview' || activeKey === 'rules') actions = auditButton() + '<button class="btn" data-action="refresh">' + icon('rotate', 'sm') + '刷新</button>';
  else actions = '<button class="btn" data-action="refresh">' + icon('rotate', 'sm') + '刷新</button>';
  return '<div>' + governanceHeader(actions) + governanceTabs(activeKey) + body + '</div>';
}

/* ---------- 治理总览 ---------- */
function renderOverview() {
  const counts = bucketCounts();
  const factorCount = state.factors.length;
  const healthy = HEALTH_MODULES.filter((m) => m.status === 'healthy').length;

  const queue = [
    { kind: 'warn', icon: 'shield', label: '等你决定的规则', count: counts.todo, desc: 'AI 已给出结论，采纳后全部 Agent 立即携带；不采纳可驳回并说明原因。', nav: '#/system/rules', bucket: 'todo', go: '去处理' },
    { kind: 'info', icon: 'rotate', label: 'AI 审核进行中', count: counts.auditing, desc: '后台正在跑审核，完成后自动进入「等你决定」，无需守着页面。', nav: '#/system/rules', bucket: 'auditing', go: '查看进度' },
    { kind: 'err', icon: 'alert', label: '因子失效建议', count: factorCount, desc: '连续 3 个月预测力接近 0，是否退出每日打分由你决定。', nav: '#/system/factors', bucket: '', go: '去决策' },
    { kind: 'ok', icon: 'undo', label: '已回滚的规则', count: counts.rolled_back, desc: '全部 Agent 已停止携带，审计记录仍可追溯。', nav: '#/system/rules', bucket: 'rolled_back', go: '查看留痕' }
  ];

  const stats = [
    { label: 'Agent / Workflow', value: '8 / 9', sub: '决策单元与协作流程' },
    { label: '只读工具', value: 12, sub: '本页不触发任何写操作' },
    { label: '协作白名单', value: 21, sub: '未声明的 1320 条默认禁止' },
    { label: '健康模块', value: healthy + '/' + HEALTH_MODULES.length, sub: healthy === HEALTH_MODULES.length ? '全部正常' : '其余需关注', tone: healthy === HEALTH_MODULES.length ? 'ok' : 'warn' }
  ];

  const events = GOV_EVENTS.slice(0, 6);

  return renderGovernanceShell('overview',
    '<div class="stack">' +
      '<div class="queue-grid">' + queue.map((q) =>
        '<button class="queue-card ' + q.kind + '" data-nav="' + q.nav + '" data-bucket="' + q.bucket + '">' +
          '<div class="queue-top"><span class="queue-icon">' + icon(q.icon, 'sm') + '</span><span class="queue-label">' + esc(q.label) + '</span></div>' +
          '<div class="queue-main"><span class="queue-count">' + q.count + '</span><span class="queue-unit">' + (q.count === 0 ? '当前没有' : '项') + '</span></div>' +
          '<div class="queue-desc">' + esc(q.desc) + '</div>' +
          '<div class="queue-go">' + esc(q.go) + icon('arrow', 'sm') + '</div>' +
        '</button>'
      ).join('') + '</div>' +

      '<div class="metric-strip">' + stats.map((s) =>
        '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div><div class="metric-value ' + (s.tone || '') + '">' + esc(s.value) + '</div><div class="metric-sub">' + esc(s.sub) + '</div></div>'
      ).join('') + '</div>' +

      '<div class="overview-split">' +
        '<div class="card">' +
          '<div class="card-title"><h3>治理模块健康度</h3><span class="hint">只读 · 按模块聚合</span></div>' +
          '<div class="table-wrap"><table>' +
            '<thead><tr><th>模块</th><th>状态</th><th>关键数字</th><th>问题</th><th>建议</th><th></th></tr></thead><tbody>' +
            HEALTH_MODULES.map((m) =>
              '<tr>' +
                '<td><span class="health-title">' + esc(m.name) + '</span></td>' +
                '<td>' + statusTag('', m.status) + '</td>' +
                '<td class="small dim">' + esc(m.counts) + '</td>' +
                '<td class="health-reason">' + esc(m.reason) + '</td>' +
                '<td class="health-action">' + esc(m.action) + '</td>' +
                '<td>' + (m.link ? '<button class="btn link sm" data-nav="' + m.link + '">' + esc(m.linkLabel) + '</button>' : '<span class="muted small">—</span>') + '</td>' +
              '</tr>'
            ).join('') +
          '</tbody></table></div>' +
        '</div>' +
        '<div class="stack">' +
          '<div class="card">' +
            '<div class="card-title"><h3>治理原则</h3></div>' +
            '<div class="influence-list">' +
              '<div class="influence-item">' + icon('ban') + '<div><b>未声明即禁止</b><span>协作矩阵未声明的关系默认拒绝，不做猜测。</span></div></div>' +
              '<div class="influence-item">' + icon('link') + '<div><b>变更必须留痕</b><span>规则采纳、回滚和偏好修改都写入审计记录。</span></div></div>' +
              '<div class="influence-item">' + icon('alert') + '<div><b>回测不自动生效</b><span>因子 IC 只出结论，下线必须人工确认。</span></div></div>' +
              '<div class="influence-item">' + icon('shield') + '<div><b>人工门禁优先</b><span>建仓、卖出、复盘建议都必须人工确认。</span></div></div>' +
            '</div>' +
          '</div>' +
          '<div class="card">' +
            '<div class="card-title"><h3>最近留痕</h3><button class="btn link sm" data-nav="#/system/rules" data-bucket="all">查看全部</button></div>' +
            '<div class="timeline">' + events.map((e) =>
              '<div class="tl-item"><span class="tl-dot ' + (e.tone || '') + '"></span>' +
                '<div class="tl-head"><span class="tl-title">' + esc(e.title) + '</span>' + actorChip(e) + '<span class="tl-time">' + esc(relTime(e.time)) + '</span></div>' +
                '<div class="tl-body">' + esc(e.body) + '</div></div>'
            ).join('') + '</div>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</div>'
  );
}

/* ---------- 规则审计 ---------- */
function ruleListHtml(list) {
  if (!list.length) return '<div class="empty-list"><strong>这个队列现在是空的</strong>换一个队列，或清空筛选条件看看其余规则。</div>';
  const q = state.ruleQuery.trim();
  return list.map((r) => {
    const active = r.id === state.selectedRuleId;
    const canAct = r.status === 'pending' && r.audit === 'pass';
    const canCheck = r.status === 'pending';
    const checked = state.ruleChecked.includes(r.id);
    return '<div role="button" tabindex="0" class="rule-row ' + (active ? 'active' : '') + '" data-action="select-rule" data-id="' + r.id + '">' +
      (canCheck ? '<input type="checkbox" class="rr-check" data-check="' + r.id + '" ' + (checked ? 'checked' : '') + ' aria-label="选择 ' + esc(r.name) + '" />' : '') +
      '<div class="rr-top"><span class="rr-name">' + highlight(r.name, q) + '</span>' + rulePill(r) + '</div>' +
      '<div class="rr-reason">' + highlight(r.reason, q) + '</div>' +
      '<div class="rr-foot"><span>' + esc(agentLabel(r.agent)) + ' · ' + esc((RULE_TYPE[r.type] || {}).label || r.type) + '</span>' +
        '<span class="rr-time">' + esc(relTime(r.createdAt)) + '</span>' +
        (canAct ? '<span class="rr-quick">' +
          '<button class="btn xs" data-action="quick-approve" data-id="' + r.id + '">' + icon('check', 'sm') + '采纳</button>' +
          '<button class="btn xs danger" data-action="quick-reject" data-id="' + r.id + '">驳回</button>' +
        '</span>' : '') +
      '</div>' +
    '</div>';
  }).join('');
}

function ruleBucketsHtml() {
  const counts = bucketCounts();
  const tabs = [
    { key: 'todo', label: '待我处理' }, { key: 'auditing', label: 'AI 审核中' },
    { key: 'active', label: '已生效' }, { key: 'rejected', label: '已驳回' },
    { key: 'rolled_back', label: '已回滚' }, { key: 'all', label: '全部' }
  ];
  return tabs.map((t) =>
    '<button class="rule-chip ' + (state.ruleBucket === t.key ? 'active' : '') + '" data-action="rule-bucket" data-bucket="' + t.key + '">' +
      t.label + '<span class="n">' + (counts[t.key] || 0) + '</span></button>'
  ).join('');
}

/* ---------- 批量操作 ---------- */
function checkedPending() {
  return state.rules.filter((r) => state.ruleChecked.includes(r.id) && r.status === 'pending');
}

function batchBarHtml() {
  const ids = state.ruleChecked;
  if (!ids.length) return '';
  const n = ids.length;
  if (state.batchAction === 'approve' || state.batchAction === 'reject') {
    const isReject = state.batchAction === 'reject';
    return '<div class="batch-bar">' +
      '<b>批量' + (isReject ? '驳回' : '采纳') + ' ' + n + ' 条</b>' +
      '<span class="muted">' + (isReject ? '同一个驳回原因会写入每条规则的留痕。' : '生效值使用各自 AI 建议值，可逐条调整后再操作。') + '</span>' +
      '<span class="spacer"></span>' +
      '<button class="btn ghost sm" data-action="batch-cancel">取消</button>' +
      '<button class="btn sm ' + (isReject ? 'danger' : 'primary') + '" data-action="batch-confirm" data-kind="' + state.batchAction + '">' +
        (isReject ? '确认驳回' : '确认采纳') + '</button>' +
      (isReject ? '<textarea id="batch-reason" class="batch-note" rows="2" placeholder="驳回原因（必填，写入每条留痕）"></textarea>' : '') +
    '</div>';
  }
  return '<div class="batch-bar">' +
    '<b>已选 ' + n + ' 条</b>' +
    '<span class="spacer"></span>' +
    '<button class="btn sm primary" data-action="batch-start" data-kind="approve">' + icon('check', 'sm') + '批量采纳</button>' +
    '<button class="btn sm danger" data-action="batch-start" data-kind="reject">批量驳回</button>' +
    '<button class="btn ghost sm" data-action="batch-clear">清除选择</button>' +
  '</div>';
}

function batchStart(kind) {
  const pend = checkedPending();
  if (!pend.length) { toast('没有可操作的规则', '勾选至少一条待处理的规则。', 'warn'); return; }
  state.batchAction = kind;
  $('#batch-slot').innerHTML = batchBarHtml();
  if (kind === 'reject') setTimeout(() => { const el = $('#batch-reason'); if (el) el.focus(); }, 0);
}

function batchCancel() {
  state.batchAction = null;
  $('#batch-slot').innerHTML = batchBarHtml();
}

function batchConfirm(kind) {
  let pend = checkedPending();
  if (kind === 'approve') pend = pend.filter((r) => r.audit === 'pass');
  if (!pend.length) {
    toast(kind === 'approve' ? '没有可采纳的规则' : '没有可驳回的规则',
      kind === 'approve' ? '只有 AI 审核通过的规则才能批量采纳；未通过的可批量驳回或重新审核。' : '请勾选待处理的规则。',
      'warn');
    return;
  }
  const reason = ($('#batch-reason') ? $('#batch-reason').value.trim() : '');
  if (kind === 'reject' && !reason) { toast('原因必填', '批量驳回的原因会写入每条规则的留痕。', 'warn'); return; }
  const before = pend.map((r) => clone(r));
  const now = '2026-11-16 17:' + String(20 + Math.floor(Math.random() * 30)).padStart(2, '0');
  pend.forEach((r) => {
    if (kind === 'approve') {
      r.status = 'active';
      r.current = r.suggested;
      r.timeline.push({ time: now, title: '批量采纳并生效', actor: 'human', body: '批量操作写入 rule_change，全部 Agent 下一次调用起携带。', tone: 'ok' });
    } else {
      r.status = 'rejected';
      r.timeline.push({ time: now, title: '批量驳回', actor: 'human', body: '原因：' + reason, tone: 'err' });
    }
  });
  const ids = pend.map((r) => r.id);
  state.ruleChecked = [];
  state.batchAction = null;
  state.ruleBucket = kind === 'approve' ? 'active' : 'rejected';
  refreshAll();
  syncRuleHash();
  toast(kind === 'approve' ? '批量采纳完成' : '批量驳回完成',
    ids.join('、') + ' 共 ' + ids.length + ' 条已写入留痕。', kind === 'approve' ? 'ok' : 'warn',
    {
      label: '撤销全部',
      fn: () => {
        before.forEach((snap) => {
          const idx = state.rules.findIndex((r) => r.id === snap.id);
          if (idx >= 0) state.rules[idx] = snap;
        });
        state.ruleBucket = 'todo';
        refreshAll();
        syncRuleHash();
        toast('已撤销', '批量' + (kind === 'approve' ? '采纳' : '驳回') + '已回退，未写入留痕。', 'info');
      }
    });
}

function toggleRuleCheck(id, checked) {
  const set = new Set(state.ruleChecked);
  if (checked) set.add(id); else set.delete(id);
  state.ruleChecked = [...set];
  const slot = $('#batch-slot');
  if (slot) slot.innerHTML = batchBarHtml();
}

function exportAudit() {
  const data = state.rules.map((r) => ({
    id: r.id, name: r.name, agent: r.agent, type: r.type,
    status: r.status, audit: r.audit,
    current: r.current, suggested: r.suggested,
    created_at: r.createdAt, timeline: r.timeline
  }));
  download('rule-audit-' + NOW_REF.toISOString().slice(0, 10) + '.json', JSON.stringify(data, null, 2));
  toast('已导出留痕', '共 ' + data.length + ' 条规则的完整留痕，文件在浏览器下载目录。', 'ok');
}

function renderRules(selectId) {
  const list = filteredRules();
  if (selectId) state.selectedRuleId = selectId;
  const visible = list.some((r) => r.id === state.selectedRuleId);
  if (!visible && list.length) state.selectedRuleId = list[0].id;
  if (!list.length) state.selectedRuleId = '';
  const selected = state.rules.find((r) => r.id === state.selectedRuleId) || null;

  const body =
    '<div class="subhead">' +
      '<div><h2>规则审计</h2><p>每条建议都走同一条链路：AI 审核 → 你决定 → 写入留痕。回滚和驳回必须说明原因。</p></div>' +
      '<div class="spacer"></div>' +
      '<button class="btn" data-action="export-audit" title="把当前全部规则与留痕导出为 JSON">' + icon('download', 'sm') + '导出留痕</button>' +
      auditButton() +
    '</div>' +
    '<div class="filter-bar">' +
      '<div class="search">' + icon('search') + '<input class="input" id="rule-search" placeholder="搜索规则名 / 原因 / 编号" value="' + esc(state.ruleQuery) + '" /></div>' +
      '<select id="rule-agent"><option value="">全部 Agent</option>' +
        Object.keys(AGENT_LABELS).map((id) => '<option value="' + id + '" ' + (state.ruleAgent === id ? 'selected' : '') + '>' + esc(AGENT_LABELS[id]) + '</option>').join('') +
      '</select>' +
      '<select id="rule-type"><option value="">全部类型</option>' +
        Object.keys(RULE_TYPE).map((k) => '<option value="' + k + '" ' + (state.ruleType === k ? 'selected' : '') + '>' + esc(RULE_TYPE[k].label) + '</option>').join('') +
      '</select>' +
      '<select id="rule-sort"><option value="new" ' + (state.ruleSort === 'new' ? 'selected' : '') + '>最新创建</option>' +
        '<option value="status" ' + (state.ruleSort === 'status' ? 'selected' : '') + '>待办优先</option></select>' +
      '<button class="btn ghost sm" data-action="rule-clear">清空筛选</button>' +
      '<span class="small muted">共 ' + list.length + ' 条</span>' +
    '</div>' +
    '<div class="rules-layout">' +
      '<div class="card rule-list-card">' +
        '<div class="rule-list-head"><div class="rule-filter-tabs">' + ruleBucketsHtml() + '</div></div>' +
        '<div id="batch-slot">' + batchBarHtml() + '</div>' +
        '<div class="rule-list" id="rule-list">' + ruleListHtml(list) + '</div>' +
      '</div>' +
      '<div class="rule-detail" id="rule-detail">' + (selected ? ruleDetailHtml(selected) : emptyDetailHtml()) + '</div>' +
    '</div>';

  return renderGovernanceShell('rules', body);
}

function emptyDetailHtml() {
  return '<div class="card" style="padding:40px 20px;text-align:center"><div class="muted">选择左侧任意一条规则查看详情。</div></div>';
}

function ruleDetailHtml(rule) {
  const auditMeta = AUDIT[rule.audit] || { label: rule.audit, cls: '' };
  const timeline = rule.timeline || [];
  const pending = state.pendingAction && state.pendingAction.id === rule.id ? state.pendingAction : null;

  return '<div class="card">' +
    '<div class="detail-head">' +
      '<div style="min-width:0">' +
        '<div class="detail-title">' + esc(rule.name) + '</div>' +
        '<div class="detail-sub">' + esc(rule.id) + ' · 来自 ' + esc(rule.source) + ' · ' + esc(relTime(rule.createdAt)) + '</div>' +
        '<div class="detail-tags">' + ruleState(rule) + tag(agentLabel(rule.agent), 'mute') + ruleTypeTag(rule.type) + '</div>' +
      '</div>' +
      '<div class="spacer"></div>' +
      '<div class="row">' + icon('shield', 'sm') + '<span class="small muted term" title="建仓、卖出、复盘类建议必须人工确认后才生效，系统不会自动放行。">人工门禁</span></div>' +
    '</div>' +
    (rule.audit === 'auditing' ? '<div class="progress"><div class="progress-bar"></div></div><div class="small muted">AI 正在复核样本与边界条件，完成后会自动回到「等你决定」。</div>' : '') +
    actionBarHtml(rule) +
    (pending ? inlineConfirmHtml(rule, pending) : '') +
    diffHtml(rule) +
    detailTabsHtml(rule, timeline) +
    detailBodyHtml(rule, timeline) +
  '</div>';
}

function actionBarHtml(rule) {
  let html = '';
  let notice = '';
  if (rule.status === 'pending' && rule.audit === 'pass') {
    notice = 'AI 审核已通过，等待你的决定。采纳后立即生效。';
    html = '<button class="btn primary" data-action="act-approve" data-id="' + rule.id + '">' + icon('check', 'sm') + '采纳并生效</button>' +
      '<button class="btn danger" data-action="act-reject" data-id="' + rule.id + '">' + icon('x', 'sm') + '驳回</button>' +
      '<button class="btn ghost" data-action="act-reaudit" data-id="' + rule.id + '">' + icon('rotate', 'sm') + '重新审核</button>';
  } else if (rule.status === 'pending' && rule.audit === 'fail') {
    notice = 'AI 审核未通过。请重新审核，或人工驳回并说明原因。';
    html = '<button class="btn primary" data-action="act-reaudit" data-id="' + rule.id + '">' + icon('rotate', 'sm') + '重新审核</button>' +
      '<button class="btn danger" data-action="act-reject" data-id="' + rule.id + '">' + icon('x', 'sm') + '驳回</button>' +
      '<button class="btn ghost" disabled>' + icon('check', 'sm') + '采纳（需先通过 AI 审核）</button>';
  } else if (rule.status === 'pending') {
    notice = 'AI 审核进行中，完成后会自动进入待处理。';
    html = '<button class="btn primary" data-action="act-reaudit" data-id="' + rule.id + '">' + icon('rotate', 'sm') + '重新触发审核</button>' +
      '<button class="btn ghost" data-action="act-reject" data-id="' + rule.id + '">' + icon('x', 'sm') + '驳回</button>';
  } else if (rule.status === 'active') {
    notice = '规则已生效。回滚会让全部 Agent 立即停止携带该规则。';
    html = '<button class="btn danger" data-action="act-rollback" data-id="' + rule.id + '">' + icon('undo', 'sm') + '回滚规则</button>' +
      '<button class="btn ghost" data-action="rule-detail-tab" data-tab="timeline">' + icon('clock', 'sm') + '查看留痕</button>';
  } else if (rule.status === 'rejected') {
    notice = '建议已被驳回，可重新进入人工审。';
    html = '<button class="btn" data-action="act-rereview" data-id="' + rule.id + '">' + icon('rotate', 'sm') + '重新进入人工审</button>' +
      '<button class="btn ghost" data-action="rule-detail-tab" data-tab="timeline">' + icon('clock', 'sm') + '查看留痕</button>';
  } else {
    notice = '规则已回滚，只保留审计记录，不能直接恢复。';
    html = '<button class="btn ghost" data-action="rule-detail-tab" data-tab="timeline">' + icon('clock', 'sm') + '查看留痕</button>';
  }
  return '<div class="actionbar">' + html + '<span class="notice">' + esc(notice) + '</span></div>';
}

function inlineConfirmHtml(rule, pending) {
  const kind = pending.kind;
  let title = '';
  let desc = '';
  let required = false;
  let danger = false;
  let okText = '确认';
  let placeholder = '填写备注（可选）';
  if (kind === 'approve') {
    title = '采纳后立即生效';
    desc = '将写入 rule_change，全部 Agent 在下一次调用起携带新规则。备注可选，生效值可调整。';
    okText = '确认采纳';
  } else if (kind === 'reject') {
    title = '驳回这条建议';
    desc = '驳回后该建议不会生效。原因必填，并写入留痕。';
    required = true; danger = true; okText = '确认驳回';
    placeholder = '驳回原因（必填）';
  } else if (kind === 'rollback') {
    title = '回滚这条规则';
    desc = '回滚后全部 Agent 立即停止携带该规则。原因必填，并写入 rule_change。';
    required = true; danger = true; okText = '确认回滚';
    placeholder = '回滚原因（必填）';
  }
  return '<div class="inline-confirm ' + (danger ? 'danger' : '') + '">' +
    '<div class="ic-title">' + esc(title) + '</div>' +
    '<div class="ic-desc">' + esc(desc) + '</div>' +
    (kind === 'approve' ?
      '<div class="ic-field"><label for="confirm-value">生效值</label>' +
        '<input class="input" id="confirm-value" value="' + esc(rule.suggested) + '" /></div>' : '') +
    '<textarea id="confirm-reason" rows="3" placeholder="' + esc(placeholder) + '"></textarea>' +
    '<div class="ic-actions">' +
      '<button class="btn ghost" data-action="act-cancel">取消</button>' +
      '<button class="btn ' + (danger ? 'danger' : 'primary') + '" data-action="act-confirm" data-kind="' + kind + '" data-id="' + rule.id + '">' + esc(okText) + '</button>' +
    '</div>' +
  '</div>';
}

function diffHtml(rule) {
  return '<div class="diff">' +
    '<div class="diff-box"><span class="diff-label">当前值</span><span class="diff-value">' + esc(rule.current) + '</span></div>' +
    '<div class="diff-arrow">' + icon('arrow') + '</div>' +
    '<div class="diff-box after"><span class="diff-label">建议值</span><span class="diff-value">' + esc(rule.suggested) + '</span></div>' +
  '</div>';
}

function detailTabsHtml(rule, timeline) {
  const tabs = [
    { key: 'suggestion', label: '建议内容' },
    { key: 'audit', label: 'AI 审核' },
    { key: 'timeline', label: '留痕 ' + timeline.length }
  ];
  return '<div class="detail-tabs">' + tabs.map((t) =>
    '<button class="detail-tab ' + (state.ruleDetailTab === t.key ? 'active' : '') + '" data-action="rule-detail-tab" data-tab="' + t.key + '">' + esc(t.label) + '</button>'
  ).join('') + '</div>';
}

function detailBodyHtml(rule, timeline) {
  if (state.ruleDetailTab === 'audit') return auditBodyHtml(rule);
  if (state.ruleDetailTab === 'timeline') return timelineHtml(timeline);
  return suggestionBodyHtml(rule);
}

function suggestionBodyHtml(rule) {
  return '<div class="stack">' +
    '<dl class="kv">' +
      '<dt>目标 Agent</dt><dd>' + esc(agentLabel(rule.agent)) + '</dd>' +
      '<dt>规则类型</dt><dd>' + esc((RULE_TYPE[rule.type] || {}).label || rule.type) + '</dd>' +
      '<dt>建议原因</dt><dd>' + esc(rule.reason) + '</dd>' +
      '<dt>依据</dt><dd>' + esc(rule.evidence) + '</dd>' +
      '<dt>要解决的问题</dt><dd>' + esc(rule.problem) + '</dd>' +
      '<dt>风险提示</dt><dd>' + esc(rule.risk) + '</dd>' +
      '<dt>来源复盘</dt><dd>' + esc(rule.source) + '</dd>' +
    '</dl>' +
  '</div>';
}

function auditBodyHtml(rule) {
  if (!rule.auditLog) {
    return '<div class="cap-note">' + icon('clock') + '<div>尚未完成 AI 审核。' +
      (rule.audit === 'auditing' ? '后台审核进行中，完成后会自动刷新。' : '可点击上方的「重新触发审核」。') +
      '</div></div>' +
      '<div class="stack" style="margin-top:12px"><dl class="kv">' +
        '<dt>审核轮次</dt><dd>' + esc(rule.round || 0) + '</dd>' +
        '<dt>当前状态</dt><dd>' + auditTag(rule.audit) + '</dd>' +
      '</dl></div>';
  }
  const log = rule.auditLog;
  const pct = Math.round((log.confidence || 0) * 100);
  const confCls = pct >= 80 ? '' : pct >= 60 ? 'warn' : 'err';
  return '<div class="audit-card">' +
    '<div class="audit-verdict">' +
      '<strong>AI 审核结论</strong>' +
      (log.verdict === 'pass' ? tag('通过', 'green') : tag('驳回', 'red')) +
      '<span class="small muted">第 ' + esc(log.round) + ' 轮 · ' + esc(log.model) + ' · ' + esc(log.at) + '</span>' +
      '<span class="conf"><span class="small muted">置信度 ' + pct + '%</span><span class="conf-bar"><span class="conf-fill ' + confCls + '" style="width:' + pct + '%"></span></span></span>' +
    '</div>' +
    '<div class="audit-grid">' +
      '<div><div class="audit-label">支持依据</div><div class="audit-text">' + esc(log.support) + '</div></div>' +
      '<div><div class="audit-label">反对意见</div><div class="audit-text">' + esc(log.dissent) + '</div></div>' +
      '<div><div class="audit-label">边界条件</div><div class="audit-text">' + esc(log.boundary) + '</div></div>' +
      '<div><div class="audit-label">证据引用</div><div class="audit-text">' + (log.evidenceRefs || []).map((e) => tag(e, 'outline')).join(' ') + '</div></div>' +
      '<div class="full"><div class="audit-label">建议动作</div><div class="audit-text">' +
        (log.verdict === 'pass' ? '可进入人工采纳；采纳前请确认风险提示与边界条件。' : '不建议直接采纳；请重新审核或人工驳回。') +
      '</div></div>' +
    '</div>' +
    '<details class="raw"><summary>查看原始审核记录</summary><pre>' + esc(log.reasoning) + '</pre></details>' +
  '</div>';
}

function timelineHtml(timeline) {
  if (!timeline || !timeline.length) return '<div class="empty-list"><strong>还没有留痕记录</strong>规则一旦被采纳、驳回或回滚，这里会按时间倒序记下每一步操作和原因。</div>';
  return '<div class="timeline">' + timeline.map((item) =>
    '<div class="tl-item"><span class="tl-dot ' + (item.tone || '') + '"></span>' +
      '<div class="tl-head"><span class="tl-title">' + esc(item.title) + '</span>' + actorChip(item) + '<span class="tl-time">' + esc(relTime(item.time)) + '</span></div>' +
      '<div class="tl-body">' + esc(item.body) + '</div></div>'
  ).join('') + '</div>';
}

function refreshRuleList() {
  const listEl = $('#rule-list');
  const detailEl = $('#rule-detail');
  if (!listEl || !detailEl) return;
  const list = filteredRules();
  if (!list.some((r) => r.id === state.selectedRuleId)) {
    state.selectedRuleId = list.length ? list[0].id : '';
  }
  const scroll = listEl.scrollTop;
  listEl.innerHTML = ruleListHtml(list);
  listEl.scrollTop = scroll;
  const selected = state.rules.find((r) => r.id === state.selectedRuleId) || null;
  detailEl.innerHTML = selected ? ruleDetailHtml(selected) : emptyDetailHtml();
  const countEl = $('.filter-bar .small.muted');
  if (countEl) countEl.textContent = '共 ' + list.length + ' 条';
  const listHead = $('.rule-filter-tabs');
  if (listHead) listHead.innerHTML = ruleBucketsHtml();
  const slot = $('#batch-slot');
  if (slot) slot.innerHTML = batchBarHtml();
}

function refreshRuleDetail() {
  const detailEl = $('#rule-detail');
  if (!detailEl) return;
  const selected = state.rules.find((r) => r.id === state.selectedRuleId) || null;
  detailEl.innerHTML = selected ? ruleDetailHtml(selected) : emptyDetailHtml();
}

/* ---------- 因子 ---------- */
function factorStatusLabel(row) {
  if (row.status === 'deprecated_candidate') return tag('判定失效', 'red');
  if (row.status === 'active') return tag('正常', 'green');
  return tag(row.status, 'mute');
}
function icTone(row) {
  if (row.sample < 100) return 'gold';
  if (row.ic != null && Math.abs(row.ic) >= 0.02) return 'green';
  return 'gold';
}

function renderFactors() {
  const proposals = state.factors;
  const cats = Array.from(new Set(state.factorHistory.map((r) => r.category)));
  const q = state.factorQuery.trim().toLowerCase();
  const rows = state.factorHistory
    .filter((r) => !state.factorCategory || r.category === state.factorCategory)
    .filter((r) => !q || (r.name + ' ' + r.fid + ' ' + r.period).toLowerCase().includes(q));

  const body =
    '<div class="subhead">' +
      '<div><h2>因子回测</h2><p>回测只出结论，不自动生效。是否让因子退出每日打分，由你确认并留痕。</p></div>' +
      '<div class="spacer"></div><button class="btn" data-action="refresh">' + icon('rotate', 'sm') + '刷新</button>' +
    '</div>' +

    (proposals.length ?
      '<div class="cap-note accent" style="margin-bottom:14px">' + icon('alert') + '<div><b>' + proposals.length + ' 个因子连续 3 个月预测力接近 0。</b>下线后它立即退出每日打分；驳回则继续保留。两种决定都会写入留痕。</div></div>' +
      '<div class="factor-proposals" style="margin-bottom:16px">' + proposals.map((p) =>
        '<div class="proposal-card">' +
          '<div class="proposal-head"><div style="min-width:0"><div class="proposal-name">' + esc(p.name) + '</div><div class="proposal-meta">' + esc(p.fid) + ' · ' + esc(p.category) + ' · ' + esc(p.months) + '</div></div><div class="spacer"></div><span class="state todo">等你决定</span></div>' +
          '<div class="proposal-reason">' + esc(p.reason) + '</div>' +
          '<div class="ic-values">' + p.icHistory.map((v, i) => '<span class="ic-pill">M' + (i + 1) + ' ' + v.toFixed(3) + '</span>').join('') + '</div>' +
          '<div class="proposal-actions">' +
            '<button class="btn danger sm" data-action="factor-offline" data-fid="' + p.fid + '">' + icon('ban', 'sm') + '确认下线</button>' +
            '<button class="btn ghost sm" data-action="factor-keep" data-fid="' + p.fid + '">驳回保留</button>' +
            '<span class="small muted" style="align-self:center">' + esc(p.source) + ' · ' + esc(p.at) + '</span>' +
          '</div>' +
          (state.factorConfirm === p.fid ?
            '<div class="inline-confirm danger" style="margin-top:12px">' +
              '<div class="ic-title">下线因子「' + esc(p.name) + '」</div>' +
              '<div class="ic-desc">下线后立即退出每日打分。原因必填，并写入留痕。之后可在版本记录中重新上线。</div>' +
              '<textarea id="factor-reason" rows="3" placeholder="下线原因（必填）"></textarea>' +
              '<div class="ic-actions">' +
                '<button class="btn ghost" data-action="factor-cancel">取消</button>' +
                '<button class="btn danger" data-action="factor-offline-confirm" data-fid="' + p.fid + '">确认下线</button>' +
              '</div>' +
            '</div>' : '') +
        '</div>'
      ).join('') + '</div>'
      : '<div class="cap-note" style="margin-bottom:16px">' + icon('check') + '<div>当前没有待决策的因子失效建议。</div></div>') +

    '<div class="card">' +
      '<div class="card-title"><h3>IC 月度回测历史</h3><span class="hint">|IC| < 0.02 视为无预测力；负值只代表方向相反</span></div>' +
      '<div class="filter-bar">' +
        '<div class="search">' + icon('search') + '<input class="input" id="factor-search" placeholder="搜索因子名 / ID / 月份" value="' + esc(state.factorQuery) + '" /></div>' +
        '<select id="factor-category"><option value="">全部类别</option>' + cats.map((c) => '<option value="' + esc(c) + '" ' + (state.factorCategory === c ? 'selected' : '') + '>' + esc(c) + '</option>').join('') + '</select>' +
        '<span class="small muted">共 ' + rows.length + ' 条</span>' +
      '</div>' +
      '<div class="table-wrap"><table>' +
        '<thead><tr><th>因子</th><th>ID</th><th>类别</th><th>月份</th><th class="num">IC</th><th class="num">IR</th><th class="num">胜率</th><th class="num">样本</th><th class="num">排名</th><th>状态</th></tr></thead><tbody>' +
        rows.map((r) =>
          '<tr class="clickable" data-action="factor-detail" data-id="' + r.id + '">' +
            '<td>' + esc(r.name) + '</td><td class="mono">' + esc(r.fid) + '</td><td>' + esc(r.category) + '</td><td>' + esc(r.period) + '</td>' +
            '<td class="num">' + (r.ic == null ? '—' : r.ic.toFixed(4)) + '</td>' +
            '<td class="num">' + (r.ir == null ? '—' : r.ir.toFixed(4)) + '</td>' +
            '<td class="num">' + (r.hit * 100).toFixed(1) + '%</td>' +
            '<td class="num">' + r.sample + '</td>' +
            '<td class="num">' + r.rank + '</td>' +
            '<td>' + factorStatusLabel(r) + '</td>' +
          '</tr>'
        ).join('') +
      '</tbody></table></div>' +
      (rows.length ? '' : '<div class="empty-list">没有符合筛选条件的回测记录。</div>') +
    '</div>';

  return renderGovernanceShell('factors', body);
}

function factorDetailHtml(row) {
  return '<div class="stack">' +
    '<dl class="kv">' +
      '<dt>因子</dt><dd>' + esc(row.name) + '</dd>' +
      '<dt>因子 ID</dt><dd class="mono">' + esc(row.fid) + '</dd>' +
      '<dt>类别</dt><dd>' + esc(row.category) + '</dd>' +
      '<dt>月份</dt><dd>' + esc(row.period) + '</dd>' +
      '<dt>IC / IR</dt><dd>' + (row.ic == null ? '—' : row.ic.toFixed(4)) + ' / ' + (row.ir == null ? '—' : row.ir.toFixed(4)) + '</dd>' +
      '<dt>胜率 / 样本</dt><dd>' + (row.hit * 100).toFixed(1) + '% / ' + row.sample + '</dd>' +
      '<dt>类别排名</dt><dd>' + row.rank + '</dd>' +
      '<dt>状态</dt><dd>' + factorStatusLabel(row) + '</dd>' +
    '</dl>' +
    '<div class="card" style="padding:12px">' +
      '<div class="card-title"><h3>近 6 个月 IC 走势</h3><span class="hint">零线附近波动越小，预测力越弱</span></div>' +
      sparkline([0.011, 0.006, -0.004, 0.009, -0.002, row.ic == null ? 0 : row.ic]) +
    '</div>' +
    '<div class="cap-note">' + icon('info') + '<div>|IC| 低于 0.02 通常视为无预测力；负 IC 代表方向相反，不等于失效。因子决策必须人工确认并留痕。</div></div>' +
  '</div>';
}

function sparkline(values) {
  const w = 640, h = 120, pad = 22;
  const min = Math.min(-0.02, ...values) - 0.005;
  const max = Math.max(0.02, ...values) + 0.005;
  const x = (i) => pad + (i * (w - pad * 2) / Math.max(values.length - 1, 1));
  const y = (v) => h - pad - ((v - min) / (max - min)) * (h - pad * 2);
  const pts = values.map((v, i) => x(i) + ',' + y(v)).join(' ');
  const zero = y(0);
  return '<svg class="spark" viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="IC 走势">' +
    '<line class="zero" x1="' + pad + '" y1="' + zero + '" x2="' + (w - pad) + '" y2="' + zero + '"/>' +
    '<polyline class="line" points="' + pts + '"/>' +
    values.map((v, i) => '<circle class="dot" cx="' + x(i) + '" cy="' + y(v) + '" r="3"/>').join('') +
    '<text x="' + pad + '" y="' + (zero - 4) + '">0</text>' +
    '<text x="' + (w - pad - 60) + '" y="' + (h - 4) + '">近 6 个月</text>' +
  '</svg>';
}

/* ---------- 能力地图 ---------- */
function renderCapability() {
  const stats = [
    { label: 'Agent / Workflow', value: '8 / 9', sub: '决策单元与协作流程' },
    { label: '只读工具', value: 12, sub: '只读不写，不触发执行' },
    { label: '协作白名单', value: 21, sub: '未声明的 1320 条默认禁止' },
    { label: '人工门禁', value: 4, sub: '建仓 / 卖出 / 复盘 / 监控', tone: 'info' }
  ];

  const body =
    '<div class="subhead">' +
      '<div><h2>能力地图</h2><p>只读视图：Agent、Workflow、工具与协作矩阵。本页不提供任何执行入口，想看结论点行即可。</p></div>' +
      '<div class="spacer"></div><button class="btn" data-action="refresh">' + icon('rotate', 'sm') + '刷新</button>' +
    '</div>' +
    '<div class="metric-strip" style="margin-bottom:16px">' + stats.map((s) =>
      '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div><div class="metric-value ' + (s.tone || '') + '">' + esc(s.value) + '</div><div class="metric-sub">' + esc(s.sub) + '</div></div>'
    ).join('') + '</div>' +
    '<div class="cap-note" style="margin-bottom:14px">' + icon('shield') + '<div>协作矩阵采用显式白名单：任何未声明的调用方、目标或关系都按默认禁止处理。点击 Agent 行查看职责、权限与不可做事项。</div></div>' +

    '<div class="card" style="margin-bottom:14px">' +
      '<div class="card-title"><h3>Agent 能力</h3><span class="hint">点击行查看详情</span></div>' +
      '<div class="table-wrap"><table>' +
        '<thead><tr><th>Agent</th><th>责任</th><th>类型 / 权限</th><th>知识范围</th><th>可引用</th><th>可调用</th><th>不可做</th><th>人工门禁</th></tr></thead><tbody>' +
        AGENTS.map((a) =>
          '<tr class="clickable" data-action="agent-detail" data-id="' + a.id + '">' +
            '<td><span class="agent-name"><b>' + esc(a.name) + '</b><span>' + esc(a.id) + '</span></span></td>' +
            '<td class="wrap ellipsis">' + esc(a.responsibility) + '</td>' +
            '<td>' + tag(a.type, 'outline') + ' ' + tag(a.authority, 'blue') + '</td>' +
            '<td>' + tag(a.scope, '') + '</td>' +
            '<td>' + (a.canRef.length ? a.canRef.map((x) => tag(agentLabel(x), 'outline')).join(' ') : '<span class="muted">—</span>') + '</td>' +
            '<td>' + (a.canCall.length ? a.canCall.map((x) => tag(agentLabel(x), 'green')).join(' ') : '<span class="muted">—</span>') + '</td>' +
            '<td>' + a.cannot.map((x) => tag(x, 'red')).join(' ') + '</td>' +
            '<td>' + (a.gate ? tag('需要', 'gold') : tag('不需要', 'green')) + '</td>' +
          '</tr>'
        ).join('') +
      '</tbody></table></div>' +
    '</div>' +

    '<details class="section" style="margin-bottom:14px"><summary>Workflow（9 个人机协作流程）</summary><div class="section-body">' +
      '<div class="table-wrap"><table><thead><tr><th>Workflow</th><th>示例意图</th><th>步骤</th><th>必填输入</th><th>治理状态</th><th>最终响应</th></tr></thead><tbody>' +
      WORKFLOWS.map((w) =>
        '<tr><td><span class="agent-name"><b>' + esc(w.name) + '</b><span>' + esc(w.id) + '</span></span></td><td>' + esc(w.intent) + '</td><td class="wrap">' + esc(w.steps) + '</td><td>' + tag(w.inputs, 'outline') + '</td><td>' + esc(w.gate) + '</td><td>' + esc(w.final) + '</td></tr>'
      ).join('') + '</tbody></table></div></div></details>' +

    '<details class="section" style="margin-bottom:14px"><summary>只读工具（12 个 ReAct 工具）</summary><div class="section-body">' +
      '<div class="table-wrap"><table><thead><tr><th>工具</th><th>所属模块</th><th>描述</th><th>使用方</th><th>类型</th></tr></thead><tbody>' +
      TOOLS.map((t) =>
        '<tr><td>' + esc(t.name) + '<div class="small muted mono">' + esc(t.id) + '</div></td><td>' + esc(t.owner) + '</td><td class="wrap">' + esc(t.desc) + '</td><td class="wrap small dim">' + esc(t.usedBy) + '</td><td>' + tag('只读', 'green') + '</td></tr>'
      ).join('') + '</tbody></table></div></div></details>' +

    '<div class="card">' +
      '<div class="card-title"><h3>协作矩阵</h3><span class="hint">显式白名单 · 未声明即禁止</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>调用方</th><th>目标</th><th>关系</th><th>允许</th><th>最大深度</th><th>冲突策略</th><th>需审计</th><th>原因</th></tr></thead><tbody>' +
      COLLAB_RULES.map((r) =>
        '<tr><td>' + tag(agentLabel(r.requester), 'blue') + '</td><td>' + tag(agentLabel(r.target), 'outline') + '</td><td>' + esc(r.relation) + '</td><td>' + (r.allowed ? tag('允许', 'green') : tag('默认禁止', 'red')) + '</td><td>' + r.depth + '</td><td>' + esc(r.policy) + '</td><td>' + (r.audit ? tag('需要', 'gold') : tag('不需要', 'green')) + '</td><td class="wrap small dim">' + esc(r.reason) + '</td></tr>'
      ).join('') + '</tbody></table></div>' +
      '<div class="card" style="background:var(--bg-input);margin-top:12px">' +
        '<div class="card-title"><h3>只读协作查询</h3></div>' +
        '<div class="filter-bar">' +
          '<select id="collab-requester"><option value="">调用方</option>' + AGENTS.map((a) => '<option value="' + a.id + '">' + esc(a.name) + '</option>').join('') + '</select>' +
          '<select id="collab-target"><option value="">目标</option>' + AGENTS.map((a) => '<option value="' + a.id + '">' + esc(a.name) + '</option>').join('') + '</select>' +
          '<select id="collab-relation"><option value="call">call</option><option value="reference">reference</option><option value="propose_change">propose_change</option></select>' +
          '<button class="btn primary sm" data-action="collab-query">' + icon('search', 'sm') + '查询</button>' +
        '</div>' +
        '<div id="collab-result">' + collabResultHtml() + '</div>' +
      '</div>' +
    '</div>';

  return renderGovernanceShell('capability', body);
}

function collabResultHtml() {
  const r = state.collabResult;
  if (!r) return '<div class="small muted">选择调用方、目标和关系后查询是否允许协作。</div>';
  if (!r.requester || !r.target) return '<div class="small muted">请完整选择调用方和目标。</div>';
  if (r.allowed) {
    return '<div class="query-result"><span class="tag green">允许</span> <span class="small dim">' + esc(agentLabel(r.requester)) + ' → ' + esc(agentLabel(r.target)) + ' · ' + esc(r.relation) + '</span>' +
      '<div class="small muted" style="margin-top:4px">' + esc(r.reason) + ' · 需审计：' + (r.audit ? '是' : '否') + '</div></div>';
  }
  return '<div class="query-result"><span class="tag red">默认禁止</span> <span class="small dim">' + esc(agentLabel(r.requester)) + ' → ' + esc(agentLabel(r.target)) + ' · ' + esc(r.relation) + '</span>' +
    '<div class="small muted" style="margin-top:4px">协作矩阵未声明该关系，按 fail-closed 拒绝。</div></div>';
}

/* ---------- 占位页 ---------- */
function renderPlaceholder(info) {
  return '<div class="page-head"><div><div class="page-title">' + esc(info.title) + '</div><div class="page-sub">' + esc(info.desc) + '</div></div></div>' +
    '<div class="card placeholder-card">' +
      '<h2>本批次只交付「系统治理流」</h2>' +
      '<p>这一页暂用占位说明，避免用半成品误导验收。下一批会按同样的原则重做：结论先行、流程贯通、详情就地展开。</p>' +
      '<ul class="scope-list">' + info.scope.map((s) => '<li>' + esc(s) + '</li>').join('') + '</ul>' +
      '<div class="row" style="margin-top:16px">' +
        '<button class="btn primary" data-nav="#/system/overview">' + icon('shield', 'sm') + '查看治理原型</button>' +
        '<button class="btn" data-action="open-drawer" data-drawer="notes">查看导航设计说明</button>' +
      '</div>' +
    '</div>';
}

/* ---------- 工作台总览 ---------- */
const WO_MARKET = {
  indices: [
    { name: '上证指数', value: '3268.45', pct: 0.62 },
    { name: '深证成指', value: '10461.20', pct: 0.85 },
    { name: '创业板指', value: '2175.63', pct: 1.12 }
  ],
  band: '震荡偏强', score: 72, amount: '1.24 万亿',
  sectors: [
    { name: '半导体', pct: 2.14 }, { name: '光伏', pct: 1.62 }, { name: '军工', pct: 1.08 }
  ],
  overnight: { label: '纳指期货 +0.42%', band: '偏多', note: '预测偏多 · 不押注' }
};

const WO_CANDIDATES = [
  { code: '603501', name: '韦尔股份', score: 88, tier: 'A', reason: '半导体主线放量，板块资金净流入' },
  { code: '002049', name: '紫光国微', score: 84, tier: 'A', reason: '国产替代逻辑延续，机构评级上调' },
  { code: '600893', name: '航发动力', score: 81, tier: 'B', reason: '军工景气延续，量价配合良好' }
];
const WO_CANDIDATE_TOTAL = 8;
const WO_CANDIDATE_PASS = 3;

const WO_HOLDINGS = [
  { code: '600519', name: '贵州茅台', price: '1412.00', today: -1.02, note: '回撤 7.2% 已过止损线 7%', state: '红线预警' },
  { code: '300750', name: '宁德时代', price: '268.40', today: 1.35, note: '浮盈 +18.4%，接近止盈线 20%', state: '接近止盈' },
  { code: '002415', name: '海康威视', price: '31.26', today: -2.30, note: '今日放量下跌，量能未收敛', state: '关注' }
];
const WO_HOLD_SUMMARY = { total: '486,200', todayPnl: 3420, todayPct: 0.71, count: 6, redline: 1 };

const WO_TP_PLANS = [
  { code: '300750', name: '宁德时代', body: '分两档 20% / 25%，第一档进入观察区。' },
  { code: '600519', name: '贵州茅台', body: '维持 7% 止损，未上移。' },
  { code: '601012', name: '隆基绿能', body: '止盈上移至 +15%，锁定利润。' }
];

const WO_TASKS = [
  { title: '单条 AI 审核 · 追高容忍度', sub: '第 2 轮审核 · 完成后自动进入「等你决定」', status: 'run', progress: 65 },
  { title: '每日挖掘', sub: '17:02 完成 · 产出候选 8 只', status: 'done' },
  { title: '全持仓监控', sub: '15:01 完成 · 6 只持仓 · 触发 1 条红线', status: 'done' }
];

const WO_EVENTS = [
  { time: '16:48', title: '告警触发：600519 跌破止损红线', body: '已推送提醒，待人工确认处置。', tone: 'err', actor: 'sys' },
  { time: '15:01', title: '全持仓监控完成', body: '6 只持仓全部巡检，触发红线 1 条。', tone: 'info', actor: 'sys' },
  { time: '14:32', title: '建仓方案生成：韦尔股份', body: '分三档买入，等人工确认后生效。', tone: 'info', actor: 'ai' },
  { time: '11:20', title: '评分完成：今日候选 8 只', body: '3 只评分达标，进入可建仓观察。', tone: 'info', actor: 'ai' },
  { time: '09:47', title: 'AI 审核驳回：单股最大仓位上限', body: '与个人偏好 15% 冲突，转人工确认。', tone: 'err', actor: 'ai' },
  { time: '09:30', title: '数据同步完成', body: '云端 3.7 万行，同步水位正常。', tone: 'info', actor: 'sys' }
];

function woEntry(e, nav, iconName) {
  return '<div class="wo-entry" data-nav="' + nav + '">' +
    icon(iconName) +
    '<div class="wo-e-main"><div class="wo-e-name">' + esc(e.name) + '</div>' +
    '<div class="wo-e-desc">' + esc(e.desc) + '</div></div>' +
    '<span class="wo-e-go">处理 ' + icon('arrow', 'sm') + '</span>' +
  '</div>';
}

function renderWorkspaceOverview() {
  const pendingRules = state.rules.filter((r) => r.status === 'pending' && r.audit !== 'auditing');
  const pendingFactors = state.factors;
  const decisions = pendingRules.map((r) => ({
    name: r.name + ' · ' + r.id,
    desc: r.audit === 'pass' ? 'AI 已通过，等你拍板' : 'AI 未通过：' + (r.risk || '与现有规则冲突'),
    nav: '#/system/rules?bucket=todo&id=' + r.id,
    icon: 'shield'
  })).concat(pendingFactors.map((f) => ({
    name: f.name + ' · ' + f.fid,
    desc: '近 3 个月 IC 走弱，建议下线',
    nav: '#/system/factors',
    icon: 'chart'
  })));

  const cards =
    '<div class="wo-actions">' +
      '<div class="wo-card warn">' +
        '<div class="wo-head">' + icon('check') + '<span class="wo-title">需要你决策</span><span class="wo-count">' + decisions.length + ' 件待处理</span></div>' +
        '<div class="wo-entries">' + (decisions.length ? decisions.map((d) => woEntry(d, d.nav, d.icon)).join('') : '<div class="wo-empty">暂无待决策事项，治理队列都是最新的。</div>') + '</div>' +
        '<div class="wo-foot"><button class="btn link sm" data-nav="#/system/overview">进入治理工作区 ' + icon('arrow', 'sm') + '</button></div>' +
      '</div>' +
      '<div class="wo-card info">' +
        '<div class="wo-head">' + icon('star') + '<span class="wo-title">可建仓候选</span><span class="wo-count">今日 ' + WO_CANDIDATE_TOTAL + ' 只 · ' + WO_CANDIDATE_PASS + ' 只达标</span></div>' +
        '<div class="wo-entries">' + WO_CANDIDATES.map((c) => woEntry({
          name: c.name + ' ' + c.code,
          desc: '评分 ' + c.score + ' · ' + c.tier + ' 档 · ' + c.reason
        }, '#/candidates?id=' + c.code, 'plan')).join('') + '</div>' +
        '<div class="wo-foot"><button class="btn link sm" data-nav="#/candidates">进入候选池 ' + icon('arrow', 'sm') + '</button></div>' +
      '</div>' +
      '<div class="wo-card err">' +
        '<div class="wo-head">' + icon('alert') + '<span class="wo-title">持仓风控</span><span class="wo-count">' + WO_HOLD_SUMMARY.redline + ' 条红线 · 2 项关注</span></div>' +
        '<div class="wo-entries">' + WO_HOLDINGS.map((h) => woEntry({
          name: h.name + ' ' + h.code,
          desc: (h.today >= 0 ? '+' : '') + h.today.toFixed(2) + '% 今日 · ' + h.note
        }, h.state === '红线预警' ? '#/alerts' : '#/holdings', h.state === '红线预警' ? 'bell' : 'shield')).join('') + '</div>' +
        '<div class="wo-foot"><button class="btn link sm" data-nav="#/holdings">进入持仓监控 ' + icon('arrow', 'sm') + '</button></div>' +
      '</div>' +
      '<div class="wo-card ok">' +
        '<div class="wo-head">' + icon('review') + '<span class="wo-title">复盘与沉淀</span><span class="wo-count">3 笔待复盘</span></div>' +
        '<div class="wo-entries">' +
          woEntry({ name: '今日模拟平仓 2 笔', desc: '合计盈亏 +1,860，尚未写复盘结论' }, '#/reviews', 'review') +
          woEntry({ name: '经验沉淀待确认 1 条', desc: '「止损纪律执行偏差」关联规则建议待审' }, '#/experience', 'book') +
        '</div>' +
        '<div class="wo-foot"><button class="btn link sm" data-nav="#/reviews">进入交易复盘 ' + icon('arrow', 'sm') + '</button></div>' +
      '</div>' +
    '</div>';

  const market =
    '<div class="wo-market">' +
      WO_MARKET.indices.map((i) =>
        '<div class="wo-idx"><span class="wo-idx-name">' + esc(i.name) + '</span>' +
        '<span class="wo-idx-val">' + esc(i.value) + '</span>' +
        '<span class="wo-idx-pct ' + (i.pct >= 0 ? 'wo-up' : 'wo-down') + '">' + (i.pct >= 0 ? '+' : '') + i.pct.toFixed(2) + '%</span></div>'
      ).join('') +
      '<span class="wo-sep"></span>' +
      '<span class="wo-band">' + esc(WO_MARKET.band) + ' · ' + WO_MARKET.score + ' 分</span>' +
      '<span class="wo-dim">成交 ' + esc(WO_MARKET.amount) + '</span>' +
      '<span class="wo-sep"></span>' +
      WO_MARKET.sectors.map((s) =>
        '<span class="wo-sector">' + esc(s.name) + ' <b class="' + (s.pct >= 0 ? 'wo-up' : 'wo-down') + '">' + (s.pct >= 0 ? '+' : '') + s.pct.toFixed(2) + '%</b></span>'
      ).join('') +
      '<span class="wo-sep"></span>' +
      '<span class="wo-overnight">' + icon('compass') + esc(WO_MARKET.overnight.label) + ' · ' + esc(WO_MARKET.overnight.band) + '<i>' + esc(WO_MARKET.overnight.note) + '</i></span>' +
    '</div>';

  const holdCard =
    '<div class="card">' +
      '<div class="card-title"><h3>持仓摘要</h3><button class="btn link sm" data-nav="#/holdings">查看全部 ' + icon('arrow', 'sm') + '</button></div>' +
      '<div class="metric-strip">' +
        '<div class="metric"><div class="metric-label">总市值</div><div class="metric-value">' + esc(WO_HOLD_SUMMARY.total) + '</div><div class="metric-sub">模拟账户</div></div>' +
        '<div class="metric"><div class="metric-label">今日盈亏（推算）</div><div class="metric-value ' + (WO_HOLD_SUMMARY.todayPnl >= 0 ? 'up' : 'down') + '">+' + WO_HOLD_SUMMARY.todayPnl.toLocaleString() + '</div><div class="metric-sub">+' + WO_HOLD_SUMMARY.todayPct.toFixed(2) + '%</div></div>' +
        '<div class="metric"><div class="metric-label">持仓标的</div><div class="metric-value">' + WO_HOLD_SUMMARY.count + '</div><div class="metric-sub">有效持仓</div></div>' +
        '<div class="metric"><div class="metric-label">红线预警</div><div class="metric-value err">' + WO_HOLD_SUMMARY.redline + '</div><div class="metric-sub">需人工确认</div></div>' +
      '</div>' +
      '<div class="wo-entries" style="margin-top:6px">' + WO_HOLDINGS.map((h) =>
        '<div class="wo-entry" data-nav="' + (h.state === '红线预警' ? '#/alerts' : '#/holdings') + '">' +
          '<span class="hold-dot ' + (h.state === '红线预警' ? 'err' : h.state === '接近止盈' ? 'warn' : 'info') + '"></span>' +
          '<div class="wo-e-main"><div class="wo-e-name">' + esc(h.name) + ' <span class="mono dim">' + esc(h.code) + '</span></div>' +
          '<div class="wo-e-desc">' + esc(h.note) + '</div></div>' +
          '<span class="mono ' + (h.today >= 0 ? 'wo-up' : 'wo-down') + '">' + (h.today >= 0 ? '+' : '') + h.today.toFixed(2) + '%</span>' +
        '</div>'
      ).join('') + '</div>' +
    '</div>';

  const tpCard =
    '<div class="card">' +
      '<div class="card-title"><h3>移动止盈计划</h3><span class="hint">只读摘要</span></div>' +
      '<div class="stack">' + WO_TP_PLANS.map((p) =>
        '<div class="wo-tp"><b>' + esc(p.name) + '</b><span class="mono dim">' + esc(p.code) + '</span><p>' + esc(p.body) + '</p></div>'
      ).join('') + '</div>' +
    '</div>';

  const taskCard =
    '<div class="card">' +
      '<div class="card-title"><h3>后台任务</h3><button class="btn link sm" data-action="task-center">任务中心 ' + icon('arrow', 'sm') + '</button></div>' +
      '<div class="stack">' + WO_TASKS.map((t) =>
        '<div class="wo-task">' +
          '<div class="row"><b>' + esc(t.title) + '</b><span class="spacer"></span>' + (t.status === 'run' ? '<span class="state run">进行中</span>' : '<span class="state done">已完成</span>') + '</div>' +
          (t.status === 'run' ? '<div class="progress"><div class="progress-bar" style="width:' + t.progress + '%"></div></div>' : '') +
          '<div class="small muted">' + esc(t.sub) + '</div>' +
        '</div>'
      ).join('') + '</div>' +
    '</div>';

  const eventCard =
    '<div class="card">' +
      '<div class="card-title"><h3>最近留痕</h3><button class="btn link sm" data-nav="#/system/overview">全部留痕 ' + icon('arrow', 'sm') + '</button></div>' +
      '<div class="timeline">' + WO_EVENTS.map((ev) =>
        '<div class="tl-item"><span class="tl-dot ' + (ev.tone || 'info') + '"></span>' +
          '<div class="tl-head"><span class="tl-title">' + esc(ev.title) + '</span>' + actorChip(ev) + '<span class="tl-time">' + esc(ev.time) + '</span></div>' +
          '<div class="tl-body">' + esc(ev.body) + '</div>' +
        '</div>'
      ).join('') + '</div>' +
    '</div>';

  const body =
    '<div class="subhead">' +
      '<div><h2>下午好</h2><p>11 月 16 日 周一 · A 股已收盘 · 数据截至 17:30</p></div>' +
      '<div class="spacer"></div>' + tag('已收盘', 'outline') +
    '</div>' +
    '<div class="cap-note warn" style="margin-bottom:16px">' + icon('clock') +
      '<div><b>今天有 ' + (decisions.length + WO_HOLD_SUMMARY.redline) + ' 件事需要你处理</b>：治理决策 ' + decisions.length + ' 件 · 持仓红线 ' + WO_HOLD_SUMMARY.redline + ' 条。其余均为只读摘要，不会动线上策略。</div>' +
    '</div>' +
    cards +
    market +
    '<div class="wo-hold">' + holdCard + tpCard + '</div>' +
    '<div class="wo-split">' + taskCard + eventCard + '</div>';

  return '<div>' + body + '</div>';
}

/* ---------- 每日候选池 ---------- */
const CANDIDATE_POOL = [
  {
    stock_code: '603501', stock_name: '韦尔股份', trade_date: '2026-11-16', rank: 1,
    score: 88, tier: 'A', label: '可建仓', price_zone: '102 - 106',
    snapshot: { chg: 2.85, amount: '48.2 亿', turnover: '4.1%' },
    trend: [98.6, 99.2, 100.8, 100.1, 101.5, 102.3, 101.8, 103.4],
    conclusion: '板块主线放量 + 订单能见度提升，评分 88 达到可建仓档；建议首仓不超过单股上限的 1/2，分两档买入。',
    horizon: { bias: '偏多', clarity: '中' },
    reasons: ['半导体板块主线放量，行业资金净流入连续 3 日', 'CIS 芯片需求回暖，Q4 订单能见度提升', '机构评级 30 日内上调 4 次'],
    risk: '板块拥挤度偏高，短线追高风险；若跌破 100 元整数位止损。',
    levels: '支撑 100.2 / 压力 106.5；首档买入区 102 - 104。',
    volume: '成交额 48.2 亿较 5 日均量 +62%，主力资金净流入 3.1 亿。',
    news: [
      { time: '09:45', source: '财联社', title: '半导体设备招标放量，产业链订单能见度提升', sentiment: 'pos' },
      { time: '昨日', source: '上证报', title: 'CIS 传感器四季度出货指引上调', sentiment: 'pos' }
    ],
    traces: [
      { source: 'Discover', time: '11-16 09:12', summary: '候选挖掘：板块动量 + 量价突破，初筛通过。' },
      { source: 'Score', time: '11-16 11:20', summary: '评分 88（技术 30/题材 28/资金 30）。' },
      { source: 'MarketAudit', time: '11-16 14:05', summary: '审计有效档 A，通过率 6/7。' }
    ]
  },
  {
    stock_code: '002049', stock_name: '紫光国微', trade_date: '2026-11-16', rank: 2,
    score: 84, tier: 'A', label: '可建仓', price_zone: '78 - 81',
    snapshot: { chg: 1.92, amount: '22.6 亿', turnover: '3.3%' },
    trend: [74.2, 75.0, 75.8, 76.5, 77.4, 76.9, 78.1, 79.0],
    conclusion: '国产替代逻辑延续，特种芯片景气度独立于大盘；评级 84 分可建仓，注意估值分位偏高。',
    horizon: { bias: '偏多', clarity: '中' },
    reasons: ['特种芯片国产替代订单落地', '机构评级 30 日内上调 2 次', '股东户数连续两季下降'],
    risk: '估值分位 78%，安全边际一般。',
    levels: '支撑 75.8 / 压力 82；首档买入区 78 - 80。',
    volume: '成交 22.6 亿，量价配合良好，换手 3.3%。',
    news: [
      { time: '10:30', source: '证券时报', title: '特种芯片招标落地，国产化率目标上调', sentiment: 'pos' }
    ],
    traces: [
      { source: 'Discover', time: '11-16 09:12', summary: '候选挖掘：题材动量 + 基本面共振。' },
      { source: 'Score', time: '11-16 11:20', summary: '评分 84（技术 28/题材 30/资金 26）。' }
    ]
  },
  {
    stock_code: '600893', stock_name: '航发动力', trade_date: '2026-11-16', rank: 3,
    score: 81, tier: 'B', label: '可建仓', price_zone: '41 - 43',
    snapshot: { chg: 1.38, amount: '19.8 亿', turnover: '2.1%' },
    trend: [38.9, 39.4, 39.1, 40.0, 40.6, 41.2, 41.0, 41.8],
    conclusion: '军工景气延续，合同负债环比 +12% 指示在手订单充足；81 分可建仓，弹性中等偏稳。',
    horizon: { bias: '偏多', clarity: '低' },
    reasons: ['合同负债环比 +12%，在手订单充足', '军工板块滞后补涨', '量价结构健康'],
    risk: '历史弹性弱于题材股，需耐心持有。',
    levels: '支撑 39.5 / 压力 43.5。',
    volume: '温和放量，主力小幅净流入。',
    news: [
      { time: '08:50', source: '行业频道', title: '军工央企三季报集中披露，预收款普涨', sentiment: 'pos' }
    ],
    traces: [
      { source: 'Discover', time: '11-16 09:12', summary: '候选挖掘：基本面动量。' },
      { source: 'Score', time: '11-16 11:20', summary: '评分 81（技术 26/题材 27/资金 28）。' }
    ]
  },
  {
    stock_code: '002371', stock_name: '北方华创', trade_date: '2026-11-16', rank: 4,
    score: 79, tier: 'B', label: '建议关注', price_zone: '318 - 326',
    snapshot: { chg: 3.41, amount: '35.4 亿', turnover: '3.9%' },
    trend: [298, 301, 306, 310, 308, 314, 319, 323],
    conclusion: '设备招标放量直接受益，但当日涨幅偏大、量能未完全跟上，先观察回踩确认。',
    horizon: { bias: '偏多', clarity: '中' },
    reasons: ['半导体设备招标放量，中标 12 亿元', '板块主线核心标'],
    risk: '单日涨幅 3.4% 追高风险，等待回踩 5 日线。',
    levels: '支撑 310 / 压力 330。',
    volume: '放量上行，量能未创新高。',
    news: [
      { time: '09:45', source: '财联社', title: '半导体设备招标放量，北方华创中标 12 亿元', sentiment: 'pos' }
    ],
    traces: [
      { source: 'Discover', time: '11-16 09:12', summary: '候选挖掘：事件驱动。' },
      { source: 'Score', time: '11-16 11:20', summary: '评分 79（技术 27/题材 29/资金 23）。' }
    ]
  },
  {
    stock_code: '300399', stock_name: '天孚通信', trade_date: '2026-11-16', rank: 5,
    score: 77, tier: 'B', label: '建议关注', price_zone: '—',
    blocked: '当日涨幅超 9%，触发追高拦截',
    snapshot: { chg: 9.18, amount: '28.9 亿', turnover: '7.2%' },
    trend: [58.2, 59.8, 61.0, 60.4, 62.2, 63.5, 64.8, 66.2],
    conclusion: '光模块景气度高，但当日大涨触发追高拦截；进入观察，回踩不破 5 日线再评估。',
    horizon: { bias: '偏多', clarity: '低' },
    reasons: ['光模块订单饱满', '业绩预告超预期'],
    risk: '追高拦截：单日涨幅超 9%，追入盈亏比差。',
    levels: '支撑 61 / 压力 68。',
    volume: '换手 7.2% 显著放量，短线过热。',
    news: [
      { time: '13:10', source: '财联社', title: 'AI 算力资本开支上修，光模块需求上修', sentiment: 'pos' }
    ],
    traces: [
      { source: 'Discover', time: '11-16 09:12', summary: '候选挖掘：业绩动量。' },
      { source: 'Monitor', time: '11-16 14:32', summary: '追高拦截：涨幅超阈值，转入观察。' }
    ]
  },
  {
    stock_code: '601012', stock_name: '隆基绿能', trade_date: '2026-11-16', rank: 6,
    score: 76, tier: 'B', label: '建议关注', price_zone: '19.2 - 19.8',
    snapshot: { chg: 0.86, amount: '17.3 亿', turnover: '1.8%' },
    trend: [18.1, 18.4, 18.2, 18.7, 18.9, 19.0, 19.1, 19.3],
    conclusion: '硅料价格企稳 + 出口回暖，行业左侧信号；评分未达可建仓线，先关注量能持续性。',
    horizon: { bias: '中性', clarity: '低' },
    reasons: ['光伏组件出口数据超预期', '硅料价格企稳'],
    risk: '行业产能出清未完成，反弹持续性存疑。',
    levels: '支撑 18.4 / 压力 20.5。',
    volume: '量能温和，未有效放大。',
    news: [
      { time: '13:30', source: '板块雷达', title: '光伏组件出口数据超预期，欧洲仓单去化加快', sentiment: 'pos' }
    ],
    traces: [
      { source: 'Discover', time: '11-16 09:12', summary: '候选挖掘：行业反转信号。' },
      { source: 'Score', time: '11-16 11:20', summary: '评分 76（技术 24/题材 26/资金 26）。' }
    ]
  },
  {
    stock_code: '688981', stock_name: '中芯国际', trade_date: '2026-11-16', rank: 7,
    score: 74, tier: 'C', label: '观察', price_zone: '—',
    snapshot: { chg: -0.62, amount: '12.1 亿', turnover: '1.2%' },
    trend: [88.4, 87.6, 88.0, 87.2, 86.8, 87.5, 86.9, 86.4],
    conclusion: '代工价格仍在底部，左侧信号但右侧未确认；观察池跟踪，不入建仓队列。',
    horizon: { bias: '中性', clarity: '低' },
    reasons: ['国产替代长逻辑', '产能利用率缓慢回升'],
    risk: '代工价格尚未反转，右侧信号缺失。',
    levels: '支撑 85 / 压力 92。',
    volume: '缩量整理。',
    news: [],
    traces: [
      { source: 'Discover', time: '11-16 09:12', summary: '候选挖掘：长逻辑观察。' }
    ]
  },
  {
    stock_code: '000725', stock_name: '京东方A', trade_date: '2026-11-16', rank: 8,
    score: 71, tier: 'C', label: '观察', price_zone: '—',
    snapshot: { chg: -1.85, amount: '9.8 亿', turnover: '1.5%' },
    trend: [4.32, 4.28, 4.30, 4.24, 4.21, 4.18, 4.15, 4.12],
    conclusion: '面板价格环比回落，利空落地但右侧未起；观察池继续跟踪价格拐点。',
    horizon: { bias: '偏空', clarity: '中' },
    reasons: ['面板价格弱反弹后回落'],
    risk: '三季度面板价格环比回落 3%，短期承压。',
    levels: '支撑 4.05 / 压力 4.35。',
    volume: '量能萎缩。',
    news: [
      { time: '14:18', source: '公司公告', title: '京东方A：三季度面板价格环比回落 3%', sentiment: 'neg' }
    ],
    traces: [
      { source: 'Discover', time: '11-16 09:12', summary: '候选挖掘：行业周期观察。' }
    ]
  }
];

const CAND_NEWS = [
  { time: '09:45', source: '财联社', title: '半导体设备招标放量，北方华创中标 12 亿元', sentiment: 'pos', codes: ['002371', '603501'] },
  { time: '10:30', source: '证券时报', title: '特种芯片招标落地，国产化率目标上调', sentiment: 'pos', codes: ['002049'] },
  { time: '11:02', source: '证监会', title: '程序化交易新规征求意见，高频费率或上调', sentiment: 'neutral', codes: [] },
  { time: '13:10', source: '财联社', title: 'AI 算力资本开支上修，光模块需求上修', sentiment: 'pos', codes: ['300399'] },
  { time: '13:30', source: '板块雷达', title: '光伏组件出口数据超预期，欧洲仓单去化加快', sentiment: 'pos', codes: ['601012'] },
  { time: '14:18', source: '公司公告', title: '京东方A：三季度面板价格环比回落 3%', sentiment: 'neg', codes: ['000725'] },
  { time: '15:05', source: '央行', title: '11 月 MLF 等量续作，资金面维持中性', sentiment: 'neutral', codes: [] },
  { time: '15:40', source: '行业频道', title: '锂电排产 12 月环比下滑，产业链价格走弱', sentiment: 'neg', codes: [] }
];

const CAND_TIER_META = {
  '可建仓': { cls: 'ok', hint: '评分达标，可进入建仓流程' },
  '建议关注': { cls: 'info', hint: '接近达标，等量能或价位确认' },
  '观察': { cls: 'mute', hint: '暂不入建仓队列' }
};

/* 压力/支撑与买入区（数值口径，用于价位尺）；接入后端后由算法给出 */
const CAND_LEVEL_NUM = {
  '603501': { sup: 100.2, res: 106.5, buy: [102, 104] },
  '002049': { sup: 75.8, res: 82, buy: [78, 80] },
  '600893': { sup: 39.5, res: 43.5, buy: [41, 43] },
  '002371': { sup: 310, res: 330, buy: [318, 326] },
  '300399': { sup: 61, res: 68, buy: [61, 63] },
  '601012': { sup: 18.4, res: 20.5, buy: [19.2, 19.8] },
  '688981': { sup: 85, res: 92, buy: null },
  '000725': { sup: 4.05, res: 4.35, buy: null }
};
CANDIDATE_POOL.forEach((c) => {
  const n = CAND_LEVEL_NUM[c.stock_code];
  if (n) Object.assign(c, n);
  c.last = (c.trend || [0])[Math.max((c.trend || []).length - 1, 0)];
});

function filteredCandidates() {
  const q = state.candQuery.trim().toLowerCase();
  return CANDIDATE_POOL
    .filter((c) => !state.candTier || c.label === state.candTier)
    .filter((c) => !q || (c.stock_name + ' ' + c.stock_code + ' ' + (c.reasons || []).join(' ')).toLowerCase().includes(q))
    .sort((a, b) => (b.score || 0) - (a.score || 0));
}

function candLabelTag(c) {
  const m = CAND_TIER_META[c.label] || { cls: 'mute' };
  return '<span class="cp-tier ' + m.cls + '">' + esc(c.label) + '</span>';
}

function candRowHtml(c) {
  const blocked = c.blocked
    ? '<div class="cp-block">' + icon('ban', 'sm') + esc(c.blocked) + '</div>'
    : '';
  const newsN = (c.news || []).length;
  return '<div class="cp-row' + (state.candId === c.stock_code ? ' active' : '') + '" role="button" tabindex="0" data-action="select-cand" data-cand="' + c.stock_code + '">' +
    '<div class="cp-row-top">' +
      '<span class="cp-name">' + esc(c.stock_name) + '<span class="mono dim">' + esc(c.stock_code) + '</span>' +
        (c.manual ? '<span class="cp-hu">人工</span>' : '') + '</span>' +
      (c.score == null ? '<span class="cp-score none">未评分</span>' : '<span class="cp-score">' + c.score + '</span>') +
      candLabelTag(c) +
    '</div>' +
    '<div class="cp-row-reason">' + esc((c.reasons && c.reasons[0]) || '') + '</div>' +
    '<div class="cp-row-foot">' +
      '<span class="mono ' + (c.snapshot.chg >= 0 ? 'wo-up' : 'wo-down') + '">' + (c.snapshot.chg >= 0 ? '+' : '') + c.snapshot.chg.toFixed(2) + '%</span>' +
      '<span class="dim">·</span><span class="small muted">' + esc(c.snapshot.amount) + '</span>' +
      (newsN ? '<span class="cp-news-badge">' + icon('news', 'sm') + newsN + '</span>' : '') +
    '</div>' +
    blocked +
  '</div>';
}

/* 情景卡：涨 / 横 / 跌 三种走法分别怎么办，用大白话写清楚，不要求读图 */
function candScenarios(c) {
  if (!c.sup || !c.res) {
    return '<div class="cp-scene"><div class="cp-scene-empty">人工加入的标的还没有价位计算。下一批分析会补上压力/支撑，届时这里会给出涨、跌、横盘三种走法的具体做法。</div></div>';
  }
  const pctUp = ((c.res / c.last - 1) * 100).toFixed(1);
  const pctDn = ((1 - c.sup / c.last) * 100).toFixed(1);
  const buy = c.buy || null;
  const above = buy && c.last > buy[1];
  const inZone = buy && c.last >= buy[0] && c.last <= buy[1];

  let where = '现价 ' + c.last + '，在支撑 ' + c.sup + ' 与压力 ' + c.res + ' 之间';
  if (buy) where = inZone ? '现价 ' + c.last + '，已在买入区 ' + buy[0] + ' - ' + buy[1] + ' 内'
    : above ? '现价 ' + c.last + '，高于买入区 ' + buy[0] + ' - ' + buy[1] + '（偏贵）'
    : '现价 ' + c.last + '，低于买入区 ' + buy[0] + ' - ' + buy[1];

  let up = '', flat = '', dn = '';
  if (c.blocked) {
    up = '拦截未解除，涨破 ' + c.res + ' 也不追；等回踩 ' + (buy ? buy[0] : c.sup) + ' 附近重新评估。';
    flat = '维持观察，不建仓。重点看回落时量能是否萎缩，缩量企稳才算健康。';
    dn = '跌破 ' + c.sup + ' 直接移出候选，不再占用注意力。';
  } else if (c.label === '可建仓') {
    up = '站稳 ' + c.res + ' 后按已生成方案加第二档；突破当天不追，等次日不破 ' + c.res + ' 再加。';
    flat = above ? '现价高于买入区，先下小仓或等回踩 ' + buy[0] + ' - ' + buy[1] + ' 再下首仓。'
      : '在买入区 ' + (buy ? buy[0] + ' - ' + buy[1] : c.sup + ' 上方') + ' 下首仓，仓位不超过单股上限的 1/2。';
    dn = '跌破 ' + c.sup + ' 本次建仓作废；若已持仓，按 ' + c.sup + ' 止损离场。';
  } else if (c.label === '建议关注') {
    up = '放量突破 ' + c.res + ' 才转可建仓，缩量突破不算数，别提前动手。';
    flat = '区间内不动，盯量能：缩量整理继续等，放量下破说明走弱。';
    dn = '跌破 ' + c.sup + ' 说明逻辑没兑现，移出关注列表。';
  } else {
    up = '即使涨破 ' + c.res + ' 也不追，重新跑一次评分再决定要不要升级。';
    flat = '继续观察，回踩 ' + (buy ? buy[0] : c.sup) + ' 附近不破再评估。';
    dn = '跌破 ' + c.sup + ' 从池中移除，分析过程留档。';
  }

  return '<div class="cp-scene">' +
    '<div class="cp-scene-head"><span class="cp-scene-title">怎么做</span><span class="hint">' + esc(where) + '</span></div>' +
    '<div class="cp-sc up"><div class="cp-sc-tag">' + icon('caretUp', 'sm') + '如果继续涨</div>' +
      '<div class="cp-sc-cond">站上 ' + c.res + '（+' + pctUp + '%）</div>' +
      '<div class="cp-sc-act">' + esc(up) + '</div></div>' +
    '<div class="cp-sc flat"><div class="cp-sc-tag">' + icon('minus', 'sm') + '如果横盘</div>' +
      '<div class="cp-sc-cond">' + c.sup + ' - ' + c.res + ' 之间震荡</div>' +
      '<div class="cp-sc-act">' + esc(flat) + '</div></div>' +
    '<div class="cp-sc dn"><div class="cp-sc-tag">' + icon('caretDown', 'sm') + '如果下跌</div>' +
      '<div class="cp-sc-cond">跌破 ' + c.sup + '（-' + pctDn + '%）</div>' +
      '<div class="cp-sc-act">' + esc(dn) + '</div></div>' +
  '</div>';
}

function candNewsItem(n) {
  const sent = n.sentiment === 'pos' ? '<span class="cp-sent pos">利多</span>'
    : n.sentiment === 'neg' ? '<span class="cp-sent neg">利空</span>'
    : '<span class="cp-sent neu">中性</span>';
  return '<div class="cp-news-item">' +
    '<span class="cp-news-time">' + esc(n.time) + '</span>' + sent +
    '<div class="cp-news-main"><div class="cp-news-title">' + esc(n.title) + '</div>' +
    '<div class="cp-news-src">' + esc(n.source) + '</div></div>' +
  '</div>';
}

const TRACE_STEP = {
  Discover: { name: '候选挖掘', tone: 'info' },
  Score: { name: '评分', tone: 'info' },
  MarketAudit: { name: 'AI 审计', tone: 'ok' },
  Monitor: { name: '风控拦截', tone: 'warn' },
  人工: { name: '人工加入', tone: 'ok' }
};

function candDetailHtml(c) {
  const tabs = [
    { key: 'conclusion', label: '结论' },
    { key: 'basis', label: '理由与风险' },
    { key: 'news', label: '消息面' + ((c.news || []).length ? ' · ' + c.news.length : '') },
    { key: 'traces', label: '分析过程' }
  ];
  let tabBody = '';
  if (state.candTab === 'conclusion') {
    tabBody =
      '<div class="cp-conclusion">' + esc(c.conclusion) + '</div>' +
      '<dl class="kv">' +
        '<dt>评分</dt><dd>' + (c.score == null
          ? '<span class="cp-manual">人工加入 · 未评分</span>'
          : '<b class="cp-score-lg">' + c.score + '</b><span class="hint">· ' + esc(c.tier) + ' 档 · ' + esc(c.label) + '</span>') + '</dd>' +
        '<dt>前瞻</dt><dd>' + tag('前瞻·' + c.horizon.bias, c.horizon.bias === '偏多' ? 'blue' : 'outline') + ' <span class="hint">清晰度 ' + esc(c.horizon.clarity) + '</span></dd>' +
        '<dt>量价资金</dt><dd>' + esc(c.volume) + '</dd>' +
      '</dl>';
  } else if (state.candTab === 'basis') {
    tabBody =
      '<div class="cp-list-title">候选理由</div>' +
      '<ul class="cp-bullets">' + (c.reasons || []).map((r) => '<li>' + esc(r) + '</li>').join('') + '</ul>' +
      '<div class="cp-list-title">风险点</div>' +
      '<div class="cp-risk">' + icon('alert') + '<div>' + esc(c.risk) + '</div></div>' +
      (c.blocked ? '<div class="cp-risk">' + icon('ban') + '<div>' + esc(c.blocked) + '（系统拦截，转观察池）</div></div>' : '');
  } else if (state.candTab === 'news') {
    tabBody = (c.news || []).length
      ? '<div class="cp-news-list">' + c.news.map(candNewsItem).join('') + '</div>' +
        '<div class="cap-note" style="margin-top:10px">' + icon('info') + '<div>这里只列与「' + esc(c.stock_name) + '」直接相关的消息；盘面类消息请到行业消息雷达看全量。</div></div>'
      : '<div class="wo-empty">暂无该标的的相关消息，有新消息会自动关联到候选。</div>';
  } else {
    tabBody = '<div class="timeline">' + (c.traces || []).map((t) => {
      const m = TRACE_STEP[t.source] || { name: t.source, tone: 'info' };
      return '<div class="tl-item"><span class="tl-dot ' + m.tone + '"></span>' +
        '<div class="tl-head"><span class="tl-title">' + esc(m.name) + '</span><span class="tl-time">' + esc(t.time) + '</span></div>' +
        '<div class="tl-body">' + esc(t.summary) + '</div></div>';
    }).join('') + '</div>' +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>分析过程记录这只票从被挖出来到当前结论的每一步：谁做的、依据是什么。结论不对时可以顺着这里回放到具体环节。</div></div>';
  }

  return '<div class="card">' +
    '<div class="detail-head">' +
      '<div style="min-width:0">' +
        '<div class="detail-title">' + esc(c.stock_name) + ' <span class="mono dim">' + esc(c.stock_code) + '</span>' +
          (c.manual ? ' ' + actorChip({ actor: 'human' }) : '') + '</div>' +
        '<div class="detail-sub">' + esc(c.trade_date) + (c.rank ? ' · 排名第 ' + c.rank : '') + ' · 价格带 ' + esc(c.price_zone) + '</div>' +
        '<div class="detail-tags">' + candLabelTag(c) + (c.score == null ? '' : ' ' + tag(c.tier + ' 档', 'blue')) + '</div>' +
      '</div>' +
      '<div class="spacer"></div>' +
      '<div class="cp-acts">' +
        '<button class="btn sm" data-action="cand-kline" data-cand="' + c.stock_code + '">' + icon('chart', 'sm') + '看K线</button>' +
        '<div class="cp-ext">' + quoteUrls(c.stock_code).map((q) =>
          '<a class="btn link xs" href="' + q.url + '" target="_blank" rel="noopener noreferrer">' + esc(q.name) + ' ' + icon('external', 'sm') + '</a>').join('') + '</div>' +
        '<button class="btn primary sm" data-action="cand-gen" data-cand="' + c.stock_code + '">' + icon('plan', 'sm') + '生成建仓方案</button>' +
      '</div>' +
    '</div>' +
    candScenarios(c) +
    '<div class="detail-tabs">' + tabs.map((t) =>
      '<button class="detail-tab ' + (state.candTab === t.key ? 'active' : '') + '" data-action="cand-tab" data-tab="' + t.key + '">' + esc(t.label) + '</button>'
    ).join('') + '</div>' +
    '<div class="cp-tab-body">' + tabBody + '</div>' +
  '</div>';
}

function renderCandidates() {
  if (state.candMode === 'history') return renderCandHistory();
  const list = filteredCandidates();
  const sel = CANDIDATE_POOL.find((x) => x.stock_code === state.candId) || list[0] || CANDIDATE_POOL[0];
  const buyable = CANDIDATE_POOL.filter((c) => c.label === '可建仓').length;
  const watch = CANDIDATE_POOL.filter((c) => c.label === '建议关注').length;
  const manualN = CANDIDATE_POOL.filter((c) => c.manual).length;

  const stats = [
    { label: '今日候选', value: CANDIDATE_POOL.length, sub: manualN ? 'AI ' + (CANDIDATE_POOL.length - manualN) + ' · 人工 ' + manualN : 'Discover 产出' },
    { label: '可建仓', value: buyable, sub: '评分达标', tone: 'ok' },
    { label: '建议关注', value: watch, sub: '等确认信号', tone: 'info' },
    { label: '相关消息', value: CAND_NEWS.filter((n) => n.codes.length).length, sub: '共 ' + CAND_NEWS.length + ' 条盘面消息', tone: '' }
  ];

  const newsAll = CAND_NEWS
    .filter((n) => !state.candNewsLinked || n.codes.length)
    .filter((n) => !state.candNewsFilter || n.sentiment === state.candNewsFilter);
  const newsShown = state.candNewsOpen ? newsAll : newsAll.slice(0, 3);

  const newsStrip =
    '<div class="card cp-news-strip">' +
      '<div class="cp-news-head">' +
        '<div><h3>今日消息面</h3><span class="hint">下面这些候选就是因为这些消息才被选出来的；点标的名可跳到对应候选。</span></div>' +
        '<div class="spacer"></div>' +
        '<div class="cp-chips">' +
          [['', '全部'], ['pos', '利多'], ['neg', '利空'], ['neutral', '中性']].map((f) =>
            '<button class="cp-chip ' + (state.candNewsFilter === f[0] ? 'active' : '') + '" data-action="cand-news-filter" data-f="' + f[0] + '">' + f[1] + '</button>').join('') +
        '</div>' +
        '<label class="cp-switch"><input type="checkbox" data-action="cand-news-linked" ' + (state.candNewsLinked ? 'checked' : '') + ' />只看关联候选</label>' +
      '</div>' +
      '<div class="cp-news-list">' + (newsShown.length ? newsShown.map((n) => {
        const linked = n.codes.map((code) => {
          const cc = CANDIDATE_POOL.find((x) => x.stock_code === code);
          return cc ? '<button class="btn link xs" data-action="select-cand" data-cand="' + code + '">' + esc(cc.stock_name) + '</button>' : '';
        }).join(' ');
        return '<div class="cp-news-item">' +
          '<span class="cp-news-time">' + esc(n.time) + '</span>' +
          (n.sentiment === 'pos' ? '<span class="cp-sent pos">利多</span>' : n.sentiment === 'neg' ? '<span class="cp-sent neg">利空</span>' : '<span class="cp-sent neu">中性</span>') +
          '<div class="cp-news-main"><div class="cp-news-title">' + esc(n.title) + '</div>' +
          '<div class="cp-news-src">' + esc(n.source) + (linked ? ' · 关联：' + linked : ' <span class="dim">· 盘面消息，不针对单只票</span>') + '</div></div>' +
        '</div>';
      }).join('') : '<div class="wo-empty">当前筛选条件下没有消息。</div>') + '</div>' +
      '<div class="cp-news-foot">' +
        (newsAll.length > 3 ? '<button class="btn link sm" data-action="cand-news-expand">' + (state.candNewsOpen ? '收起，只看最近 3 条' : '展开全部 ' + newsAll.length + ' 条') + '</button>' : '<span></span>') +
        '<button class="btn link sm" data-nav="#/news-sector">去行业消息雷达看全量 ' + icon('arrow', 'sm') + '</button>' +
      '</div>' +
    '</div>';

  const addForm = state.candAddOpen ?
    '<div class="inline-confirm cp-add">' +
      '<div class="ic-title">手动加入候选池</div>' +
      '<div class="ic-desc">你自己发现的标的：填代码和理由即可入池，默认标为「人工」且不参与 AI 评分排名；价格带可留空，后续由系统补压力/支撑。</div>' +
      '<div class="cp-add-grid">' +
        '<div class="ic-field"><label for="add-code">代码 *</label><input class="input mono" id="add-code" placeholder="如 600036" /></div>' +
        '<div class="ic-field"><label for="add-name">名称 *</label><input class="input" id="add-name" placeholder="如 招商银行" /></div>' +
        '<div class="ic-field"><label for="add-label">标签</label><select id="add-label">' +
          Object.keys(CAND_TIER_META).map((k) => '<option value="' + k + '"' + (k === '观察' ? ' selected' : '') + '>' + k + '</option>').join('') + '</select></div>' +
        '<div class="ic-field"><label for="add-price">现价（可选）</label><input class="input mono" id="add-price" placeholder="如 38.6" /></div>' +
      '</div>' +
      '<div class="ic-field"><label for="add-reason">加入理由 *（会写进分析过程）</label><textarea id="add-reason" rows="2" placeholder="例如：分红率回到 6%，底部放量三天，想观察"></textarea></div>' +
      '<div class="ic-actions">' +
        '<button class="btn ghost" data-action="cand-add-cancel">取消</button>' +
        '<button class="btn primary" data-action="cand-add-submit">' + icon('plus', 'sm') + '加入候选池</button>' +
      '</div>' +
    '</div>' : '';

  const body =
    '<div class="subhead">' +
      '<div><h2>每日候选池</h2><p>Discover 每日产出候选，评分与消息面自动关联；从结论到建仓一条线，每个环节都能回放。</p></div>' +
      '<div class="spacer"></div>' +
      candModeChips() +
      '<button class="btn sm" data-action="cand-add-toggle">' + icon('plus', 'sm') + '手动加入候选</button>' +
      '<span class="mono dim">2026-11-16 批次</span>' +
    '</div>' +
    '<div class="metric-strip" style="margin-bottom:14px">' + stats.map((s) =>
      '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div><div class="metric-value ' + (s.tone || '') + '">' + esc(s.value) + '</div><div class="metric-sub">' + esc(s.sub) + '</div></div>'
    ).join('') + '</div>' +
    addForm +
    newsStrip +
    '<div class="cp-toolbar">' +
      '<div class="search">' + icon('search') + '<input class="input" id="cand-search" placeholder="搜索名称 / 代码 / 理由" value="' + esc(state.candQuery) + '" /></div>' +
      '<select id="cand-tier"><option value="">全部标签</option>' +
        Object.keys(CAND_TIER_META).map((k) => '<option value="' + k + '" ' + (state.candTier === k ? 'selected' : '') + '>' + k + '</option>').join('') +
      '</select>' +
      '<span class="small muted">' + list.length + ' 条</span>' +
    '</div>' +
    '<div class="cp-layout">' +
      '<div class="card cp-list-card"><div class="cp-list" id="cand-list">' + list.map(candRowHtml).join('') + '</div></div>' +
      '<div class="cp-detail" id="cand-detail">' + candDetailHtml(sel) + '</div>' +
    '</div>';

  return '<div>' + body + '</div>';
}

function refreshCandList() {
  const list = filteredCandidates();
  const el = $('#cand-list');
  if (el) el.innerHTML = list.map(candRowHtml).join('');
  const cnt = $('#view .cp-toolbar .small.muted');
  if (cnt) cnt.textContent = list.length + ' 条';
}

function selectCand(code) {
  state.candId = code;
  $$('.cp-row').forEach((el) => el.classList.toggle('active', el.dataset.cand === code));
  const detail = $('#cand-detail');
  const c = CANDIDATE_POOL.find((x) => x.stock_code === code);
  if (detail && c) detail.innerHTML = candDetailHtml(c);
  hydrateIcons(detail);
  syncCandHash();
}

function syncCandHash() {
  if (state.route !== '#/candidates') return;
  const next = state.candMode === 'history'
    ? '#/candidates?date=' + state.candBatch
    : '#/candidates?id=' + state.candId;
  if (location.hash !== next) history.replaceState(null, '', next);
}

/* 人工发现的标的：入池但不参与 AI 评分，标签默认观察，理由写进分析过程 */
function addManualCandidate() {
  const code = ($('#add-code').value || '').trim();
  const name = ($('#add-name').value || '').trim();
  const reason = ($('#add-reason').value || '').trim();
  const label = $('#add-label').value;
  const price = parseFloat(($('#add-price').value || '').trim());

  if (!/^\d{6}$/.test(code)) { toast('代码格式不对', '请填写 6 位股票代码，例如 600036。', 'warn'); $('#add-code').focus(); return; }
  if (!name) { toast('名称必填', '名称会显示在候选列表里，避免只有一串代码。', 'warn'); $('#add-name').focus(); return; }
  if (!reason) { toast('加入理由必填', '理由会写入分析过程，方便以后回看当时为什么关注它。', 'warn'); $('#add-reason').focus(); return; }
  if (CANDIDATE_POOL.some((c) => c.stock_code === code)) { toast('已在候选池', name + '（' + code + '）今天已经在池里了，直接搜代码就能找到。', 'info'); return; }

  const item = {
    stock_code: code, stock_name: name, trade_date: '2026-11-16', rank: 0,
    score: null, tier: '—', label: label, manual: true,
    price_zone: isFinite(price) ? String(price) : '—',
    last: isFinite(price) ? price : null, sup: null, res: null, buy: null,
    snapshot: { chg: 0, amount: '—', turnover: '—' },
    trend: [],
    conclusion: '人工加入的标的，未经 AI 评分与风控校验；先按「' + label + '」跟踪，下一批 Discover 会把它纳入同一套指标计算。',
    horizon: { bias: '中性', clarity: '低' },
    reasons: [reason],
    risk: '人工加入：暂无量化评分支撑，仓位建议单独控制。',
    levels: '暂无压力/支撑计算结果。',
    volume: '暂无量价资金计算结果。',
    news: [],
    traces: [{ source: '人工', time: '刚刚', summary: '人工加入候选池，标签「' + label + '」。理由：' + reason }]
  };
  CANDIDATE_POOL.push(item);
  state.candAddOpen = false;
  state.candId = code;
  state.candTab = 'conclusion';
  renderView();
  syncCandHash();
  toast('已加入候选池', name + '（' + code + '）标记为人工候选，暂不参与 AI 评分排名。', 'ok', {
    label: '撤销',
    fn: () => {
      const i = CANDIDATE_POOL.findIndex((c) => c.stock_code === code);
      if (i >= 0) CANDIDATE_POOL.splice(i, 1);
      state.candId = '603501';
      renderView();
      syncCandHash();
      toast('已撤销', name + ' 已从候选池移除，未写入任何记录。', 'info');
    }
  });
}

/* 外部行情页跳转：正式实现里 provider 列表放配置，这里先给东财与雪球两个稳定入口 */
function marketPrefix(code) {
  if (/^(60|68|9|5)/.test(code)) return 'sh';
  if (/^(0|2|3|1)/.test(code)) return 'sz';
  return 'bj';
}
function quoteUrls(code) {
  const p = marketPrefix(code);
  return [
    { name: '东方财富', url: 'https://quote.eastmoney.com/' + p + code + '.html' },
    { name: '雪球', url: 'https://xueqiu.com/S/' + p.toUpperCase() + code }
  ];
}

/* 示意蜡烛图：真实渲染由 web/src/components/charts/KlineChart.tsx（ECharts）负责，数据来自 /api/kline/{code} */
function mockBars(c) {
  const base = (c.trend && c.trend.length ? c.trend : [c.last || 100]);
  const seed = code5(c.stock_code);
  const n = 30;
  const bars = [];
  for (let i = 0; i < n; i++) {
    const t = (i / (n - 1)) * (base.length - 1);
    const k = Math.floor(t), f = t - k;
    const a = base[k], b = base[Math.min(k + 1, base.length - 1)];
    const close = a + (b - a) * f;
    const wob = Math.sin(i * 2.7 + seed) * 0.009;
    const open = close * (1 + wob);
    const hi = Math.max(open, close) * (1 + 0.005 + Math.abs(wob) * 0.5);
    const lo = Math.min(open, close) * (1 - 0.005 - Math.abs(wob) * 0.5);
    bars.push({ open, close, high: hi, low: lo, vol: 0.35 + Math.abs(Math.sin(i * 1.31 + seed)) * 0.65 });
  }
  return bars;
}
function code5(code) { let s = 0; for (const ch of String(code)) s += ch.charCodeAt(0); return s % 7; }

function candKlineHtml(c, anchorLabel) {
  const anch = anchorLabel || '选中日';
  const bars = mockBars(c);
  const w = 640, ph = 168, vh = 40, padL = 44, padR = 10;
  const lo = Math.min(...bars.map((b) => b.low));
  const hi = Math.max(...bars.map((b) => b.high));
  const span = hi - lo || 1;
  const bw = (w - padL - padR) / bars.length;
  const y = (v) => 12 + (1 - (v - lo) / span) * (ph - 24);
  const anchorIdx = bars.length - 7;
  const anchorX = padL + anchorIdx * bw + bw / 2;
  const ma = (p) => bars.map((_, i) => i + 1 < p ? null : bars.slice(i - p + 1, i + 1).reduce((s, b) => s + b.close, 0) / p);
  const maPath = (vals) => vals.map((v, i) => v == null ? '' : (i === 0 || vals[i - 1] == null ? 'M' : 'L') + (padL + i * bw + bw / 2) + ' ' + y(v)).join(' ');
  const candles = bars.map((b, i) => {
    const up = b.close >= b.open;
    const x = padL + i * bw + bw / 2;
    const top = y(Math.max(b.open, b.close));
    const h = Math.max(Math.abs(y(b.open) - y(b.close)), 1.5);
    const cls = up ? 'bull' : 'bear';
    return '<line class="wkl wick ' + cls + '" x1="' + x + '" y1="' + y(b.high) + '" x2="' + x + '" y2="' + y(b.low) + '"/>' +
      '<rect class="wkl body ' + cls + '" x="' + (x - bw * 0.3) + '" y="' + top + '" width="' + bw * 0.6 + '" height="' + h + '"/>' +
      '<rect class="wkl vol ' + cls + '" x="' + (x - bw * 0.3) + '" y="' + (ph + vh - 6 - b.vol * (vh - 12)) + '" width="' + bw * 0.6 + '" height="' + (b.vol * (vh - 12)) + '"/>';
  }).join('');

  return '<div class="wk">' +
    '<div class="wk-title"><b>' + esc(c.stock_code + ' ' + c.stock_name) + '</b><span class="hint">K线 · ' + esc(c.trade_date) + ' ±60日</span>' +
      '<span class="spacer"></span><span class="wk-anchor">' + esc(anch) + ' ' + esc(c.trade_date) + '</span></div>' +
    '<svg class="wk-svg" viewBox="0 0 ' + w + ' ' + (ph + vh + 10) + '" role="img" aria-label="日K线示意">' +
      [0, 0.25, 0.5, 0.75, 1].map((f) => '<line class="wk-grid" x1="' + padL + '" y1="' + (12 + f * (ph - 24)) + '" x2="' + (w - padR) + '" y2="' + (12 + f * (ph - 24)) + '"/>' +
        '<text class="wk-axis" x="' + (padL - 6) + '" y="' + (16 + f * (ph - 24)) + '">' + (hi - f * span).toFixed(2) + '</text>').join('') +
      candles +
      '<path class="wk-ma ma5" d="' + maPath(ma(5)) + '"/>' +
      '<path class="wk-ma ma20" d="' + maPath(ma(20)) + '"/>' +
      '<line class="wk-anchor-line" x1="' + anchorX + '" y1="8" x2="' + anchorX + '" y2="' + (ph + vh) + '"/>' +
      '<text class="wk-anchor-text" x="' + (anchorX + 4) + '" y="18">' + esc(anch) + '</text>' +
    '</svg>' +
    '<div class="wk-legend"><span><i class="bull"></i>阳线（涨）</span><span><i class="bear"></i>阴线（跌）</span>' +
      '<span><i class="l ma5"></i>MA5</span><span><i class="l ma20"></i>MA20</span><span>下方为成交量</span></div>' +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>正式页面直接复用现有组件 <code>KlineChart</code>（ECharts 蜡烛图 + MA + 锚点虚线），数据走 <code>GET /api/kline/{code}</code>，本地日线库已有回填任务，不需要新写图表。这里的图是示意数据。</div></div>' +
    '<div class="wk-links"><span class="hint">需要看分时/资金/研报原文时直接跳行情页：</span>' +
      quoteUrls(c.stock_code).map((q) => '<a class="btn sm" href="' + q.url + '" target="_blank" rel="noopener noreferrer">' + esc(q.name) + ' ' + icon('external', 'sm') + '</a>').join('') +
    '</div>' +
  '</div>';
}

/* ---------- 候选池历史批次 ---------- */
const CAND_BATCHES = [
  { date: '2026-11-16', total: 8, buyable: 3, opened: 0, reviewed: 0, win: null, avg: null, lessons: 0, track: 0, state: '今日盘中' },
  { date: '2026-11-13', total: 7, buyable: 2, opened: 2, reviewed: 1, win: 0.5, avg: -0.8, lessons: 1, track: 1, state: '跟踪中' },
  { date: '2026-11-12', total: 9, buyable: 4, opened: 3, reviewed: 3, win: 0.67, avg: 2.4, lessons: 2, track: 2, state: '已复盘' },
  { date: '2026-11-11', total: 11, buyable: 5, opened: 4, reviewed: 4, win: 0.75, avg: 4.1, lessons: 3, track: 3, state: '已复盘' },
  { date: '2026-11-10', total: 8, buyable: 3, opened: 3, reviewed: 3, win: 0.33, avg: -2.2, lessons: 2, track: 4, state: '已复盘' },
  { date: '2026-11-09', total: 6, buyable: 2, opened: 1, reviewed: 1, win: 1.0, avg: 5.6, lessons: 1, track: 5, state: '已复盘' },
  { date: '2026-11-06', total: 10, buyable: 4, opened: 4, reviewed: 4, win: 0.5, avg: 0.6, lessons: 2, track: 5, state: '已复盘' }
];

const CAND_BATCH_DETAIL = {
  '2026-11-12': [
    { code: '600893', name: '航发动力', label: '可建仓', score: 80, took: '已建仓', pnl: 4.2, days: 5, verdict: '逻辑兑现', reviewId: 1041 },
    { code: '601012', name: '隆基绿能', label: '可建仓', score: 78, took: '已建仓', pnl: -5.8, days: 5, verdict: '行业拐点未兑现', reviewId: 1042 },
    { code: '002371', name: '北方华创', label: '建议关注', score: 74, took: '未建仓', pnl: 3.1, days: 5, verdict: '错过，但标签判断正确', reviewId: null },
    { code: '688981', name: '中芯国际', label: '观察', score: 71, took: '未建仓', pnl: -1.2, days: 5, verdict: '观察合理', reviewId: null },
    { code: '000725', name: '京东方A', label: '观察', score: 69, took: '未建仓', pnl: -3.4, days: 5, verdict: '观察合理', reviewId: null },
    { code: '300399', name: '天孚通信', label: '建议关注', score: 76, took: '未建仓', pnl: 8.9, days: 5, verdict: '漏掉：追高拦截过严', reviewId: 1043 },
    { code: '603501', name: '韦尔股份', label: '建议关注', score: 75, took: '未建仓', pnl: 1.4, days: 5, verdict: '中性', reviewId: null }
  ],
  '2026-11-10': [
    { code: '601012', name: '隆基绿能', label: '可建仓', score: 82, took: '已建仓', pnl: -6.4, days: 5, verdict: '左侧抄底失败', reviewId: 1031 },
    { code: '600893', name: '航发动力', label: '可建仓', score: 79, took: '已建仓', pnl: 1.1, days: 5, verdict: '持平', reviewId: 1032 },
    { code: '002049', name: '紫光国微', label: '可建仓', score: 81, took: '已建仓', pnl: -2.8, days: 5, verdict: '板块退潮', reviewId: 1033 },
    { code: '688981', name: '中芯国际', label: '观察', score: 70, took: '未建仓', pnl: -0.9, days: 5, verdict: '观察合理', reviewId: null },
    { code: '000725', name: '京东方A', label: '观察', score: 68, took: '未建仓', pnl: -4.2, days: 5, verdict: '躲过一次下杀', reviewId: null },
    { code: '300399', name: '天孚通信', label: '建议关注', score: 73, took: '未建仓', pnl: 2.2, days: 5, verdict: '中性', reviewId: null },
    { code: '603501', name: '韦尔股份', label: '建议关注', score: 77, took: '未建仓', pnl: -1.6, days: 5, verdict: '躲过', reviewId: null }
  ]
};

function batchTrackLabel(b) {
  if (!b || !b.track) return '表现';
  return b.track >= 5 ? '后 5 日' : '后 ' + b.track + ' 日';
}

function batchItems(date) {
  if (CAND_BATCH_DETAIL[date]) return CAND_BATCH_DETAIL[date];
  const b = CAND_BATCHES.find((x) => x.date === date) || CAND_BATCHES[0];
  const seed = date.split('-').join('').slice(-4) * 1;
  return CANDIDATE_POOL.slice(0, Math.min(b.total, CANDIDATE_POOL.length)).map((c, i) => {
    const pnl = Math.round((((seed + i * 37) % 17) - 7) * 10) / 10;
    return {
      code: c.stock_code, name: c.stock_name, label: c.label, score: c.score,
      took: i < b.opened ? '已建仓' : '未建仓',
      pnl, days: 5,
      verdict: b.opened > i ? (pnl >= 2 ? '逻辑兑现' : pnl <= -3 ? '逻辑未兑现' : '持平') : '未参与',
      reviewId: (REVIEW_ROWS.find((rv) => rv.code === c.stock_code && rv.batch === date) || {}).id || null
    };
  });
}

function candBatchRowHtml(b) {
  const active = state.candBatch === b.date;
  const win = b.win == null ? '<span class="dim">—</span>' : '<span class="' + (b.win >= 0.5 ? 'ok-t' : 'bad-t') + '">' + Math.round(b.win * 100) + '%</span>';
  const avg = b.avg == null ? '<span class="dim">—</span>' : '<span class="mono ' + (b.avg >= 0 ? 'wo-up' : 'wo-down') + '">' + (b.avg >= 0 ? '+' : '') + b.avg.toFixed(1) + '%</span>';
  const st = b.state === '今日盘中' ? 'run' : b.state === '跟踪中' ? 'run' : 'off';
  return '<div class="cb-row' + (active ? ' active' : '') + '" role="button" tabindex="0" data-action="cand-batch" data-date="' + b.date + '">' +
    '<span class="cb-date mono">' + esc(b.date) + '</span>' +
    '<span class="cb-num">' + b.total + '</span>' +
    '<span class="cb-num">' + b.buyable + '</span>' +
    '<span class="cb-num">' + (b.opened || '—') + '</span>' +
    '<span class="cb-cell">' + win + '</span>' +
    '<span class="cb-cell">' + avg + '</span>' +
    '<span class="cb-num">' + (b.lessons || '—') + '</span>' +
    '<span class="state ' + st + '">' + esc(b.state) + '</span>' +
  '</div>';
}

function candBatchDetailHtml(date) {
  const b = CAND_BATCHES.find((x) => x.date === date);
  const items = batchItems(date);
  if (!b) return '';
  if (b.state === '今日盘中') {
    return '<div class="wo-empty">今日批次还在盘中更新，收盘后才会固化表现数据。要看当天的可建仓标的，切回「今日池」。</div>';
  }
  const rows = items.map((it) => {
    const cls = it.pnl >= 0 ? 'wo-up' : 'wo-down';
    const rv = it.reviewId ? reviewById(it.reviewId) : null;
    const review = rv
      ? '<button class="btn link xs" data-nav="#/reviews?id=' + rv.id + '">' + (rv.kind === 'shadow' ? '影子复盘' : '看复盘') + '</button>'
      : '<span class="dim">' + (it.took === '已建仓' ? '还没出复盘' : '未建仓') + '</span>';
    return '<div class="cbi-row">' +
      '<span class="cbi-name">' + esc(it.name) + '<span class="mono dim">' + esc(it.code) + '</span></span>' +
      candLabelTag({ label: it.label }) +
      '<span class="cbi-score mono">' + it.score + '</span>' +
      '<span class="cbi-took ' + (it.took === '已建仓' ? 'did' : '') + '">' + esc(it.took) + '</span>' +
      '<span class="cbi-pnl mono ' + cls + '">' + (it.pnl >= 0 ? '+' : '') + it.pnl.toFixed(1) + '%</span>' +
      '<span class="cbi-verdict">' + esc(it.verdict) + '</span>' +
      '<span class="cbi-go">' + review + '</span>' +
    '</div>';
  }).join('');

  const missed = items.filter((it) => it.took === '未建仓' && it.pnl >= 5);
  const failed = items.filter((it) => it.took === '已建仓' && it.pnl <= -3);
  const sum = [];
  if (failed.length) sum.push('<div class="cbi-note bad">' + icon('alert') + '<div><b>判错：</b>' + failed.map((f) => f.name + ' ' + f.pnl.toFixed(1) + '%（' + f.verdict + '）').join('；') + '。这几笔已进入复盘，教训会回流到经验库。</div></div>');
  if (missed.length) sum.push('<div class="cbi-note warn">' + icon('star') + '<div><b>错过：</b>' + missed.map((m) => m.name + ' +' + m.pnl.toFixed(1) + '%（当时标签「' + m.label + '」）').join('；') + '。如果是拦截规则过严，值得回规则审计页看那条规则。</div></div>');

  return '<div class="cbi-head">' +
      '<div><b>' + esc(date) + ' 批次</b><span class="hint">候选 ' + b.total + ' · 可建仓 ' + b.buyable + ' · 实际建仓 ' + b.opened + ' · 已复盘 ' + b.reviewed + ' · 产出经验 ' + b.lessons + ' 条</span></div>' +
      '<div class="spacer"></div>' +
      '<button class="btn link sm" data-nav="#/reviews?date=' + date + '">这批的复盘 ' + icon('arrow', 'sm') + '</button>' +
    '</div>' +
    '<div class="cbi-cols"><span>标的</span><span>标签</span><span>评分</span><span>是否建仓</span><span>' + batchTrackLabel(b) + '</span><span>结论</span><span></span></div>' +
    rows +
    (items.length < b.total ? '<div class="cbi-more">该批实际 ' + b.total + ' 条，原型里只放了 ' + items.length + ' 条明细做演示；正式版直接读 /candidates?date= 的全量。</div>' : '') +
    (!CAND_BATCH_DETAIL[date] ? '<div class="cbi-more">这一批的明细是原型里按日期生成的演示数据，所以只有部分标的能链到真实复盘；正式版每笔建仓离场都会自动出一份复盘。</div>' : '') +
    (sum.length ? '<div class="cbi-sum">' + sum.join('') + '</div>' : '') +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>历史批次只读：表现按建仓后最多 5 个交易日结算，最近批次还没满 5 日，表头按实际跟踪天数标注，数据来自候选快照 + 日线库。不参与今日评分与建仓流程，所以这里不能再生成建仓方案。</div></div>';
}

function renderCandHistory() {
  const done = CAND_BATCHES.filter((b) => b.win != null);
  const avgWin = done.reduce((s, b) => s + b.win, 0) / done.length;
  const avgPnl = done.reduce((s, b) => s + b.avg, 0) / done.length;
  const lessonN = CAND_BATCHES.reduce((s, b) => s + b.lessons, 0);

  const stats = [
    { label: '近 30 日批次', value: CAND_BATCHES.length, sub: '可回溯 30 天' },
    { label: '平均胜率', value: Math.round(avgWin * 100) + '%', sub: '已建仓标的，未满 5 日按至今', tone: avgWin >= 0.5 ? 'ok' : 'warn' },
    { label: '平均涨幅', value: (avgPnl >= 0 ? '+' : '') + avgPnl.toFixed(1) + '%', sub: '建仓后至今日', tone: avgPnl >= 0 ? 'up' : 'down' },
    { label: '产出经验', value: lessonN, sub: '进入经验库', tone: 'info' }
  ];

  return '<div>' +
    '<div class="subhead">' +
      '<div><h2>每日候选池</h2><p>历史批次用来回答「那天选出来的票后来怎么样了」，也是复盘和经验沉淀的源头。</p></div>' +
      '<div class="spacer"></div>' +
      candModeChips() +
      '<span class="mono dim">回溯 30 天</span>' +
    '</div>' +
    '<div class="metric-strip" style="margin-bottom:14px">' + stats.map((s) =>
      '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div><div class="metric-value ' + (s.tone || '') + '">' + esc(s.value) + '</div><div class="metric-sub">' + esc(s.sub) + '</div></div>'
    ).join('') + '</div>' +
    '<div class="cb-layout">' +
      '<div class="card cb-card">' +
        '<div class="card-title"><h3>批次</h3><span class="hint">点一行看该批表现</span></div>' +
        '<div class="cb-cols"><span>日期</span><span>候选</span><span>可建仓</span><span>建仓</span><span>胜率</span><span>均涨</span><span>经验</span><span></span></div>' +
        '<div class="cb-list">' + CAND_BATCHES.map(candBatchRowHtml).join('') + '</div>' +
      '</div>' +
      '<div class="card cb-detail" id="cb-detail">' + candBatchDetailHtml(state.candBatch) + '</div>' +
    '</div>' +
  '</div>';
}

function candModeChips() {
  return '<div class="cp-chips mode">' +
    '<button class="cp-chip ' + (state.candMode === 'today' ? 'active' : '') + '" data-action="cand-mode" data-mode="today">今日池</button>' +
    '<button class="cp-chip ' + (state.candMode === 'history' ? 'active' : '') + '" data-action="cand-mode" data-mode="history">历史批次</button>' +
  '</div>';
}

/* ---------- 交易复盘 ---------- */
const RV_STATUS = {
  pending: { label: '待你裁决', tone: 'todo' },
  thinking: { label: '重思考中', tone: 'run' },
  adopted: { label: '已采纳', tone: 'done' },
  rejected: { label: '已驳回', tone: 'off' },
  na: { label: '无需裁决', tone: 'off' }
};

const REVIEW_ROWS = [
  {
    id: 1044, code: '603501', name: '韦尔股份', batch: '2026-11-11', kind: 'real',
    entry: '2026-11-12', exit: '2026-11-16', hold: 2, entryPrice: 103.2, exitPrice: 106.9,
    pnl: 3.6, maxDD: -1.4, execOK: '按计划', verdict: '止盈兑现', status: 'pending', iter: 1,
    plan: '买入区 102–104 建仓；跌破 100（支撑）止损；触及 106.5（第一压力）先减半仓。',
    actual: '11-12 于 103.2 建仓；11-13 放量摸到 106.8 减半仓；11-16 于 106.9 清仓，全程没破位。',
    gap: '执行没偏差。问题是减仓之后，计划里没写「什么价格能再接回来」，后半段少吃了。',
    lesson: '分批止盈在这只票上是有效的。下次把回补条件一起写进计划：重新站上哪个价、量能要怎样配合。',
    sug: { kind: 'experience', title: '分批止盈后必须写明回补条件',
      detail: '凡触发分批止盈的建仓方案，必须带「回补价 + 回补条件」两个字段，缺一个就提示方案不完整。',
      impact: 'normal', to: '经验库 · 待审核' },
    src: { candidate: '2026-11-11', scoreId: 8842, planId: 5121 },
    traces: [
      { time: '2026-11-16 15:20', title: '系统自动复盘', body: '检测到清仓成交，拉取建仓/离场事实快照，生成计划与实际对照。', tone: 'info' },
      { time: '2026-11-16 15:22', title: 'AI 出结论与建议', body: '判定「止盈兑现」，建议沉淀为通用经验。', tone: 'info' },
      { time: '2026-11-16 15:22', title: '等你裁决', body: '采纳后进经验库；驳回则写明原因，AI 会重新想一版。', tone: 'warn' }
    ]
  },
  {
    id: 1043, code: '300399', name: '天孚通信', batch: '2026-11-12', kind: 'shadow',
    entry: null, exit: '2026-11-16', hold: 2, entryPrice: null, exitPrice: null,
    pnl: 8.9, maxDD: null, execOK: '被拦截', verdict: '拦截过严', status: 'pending', iter: 1,
    plan: '当日涨幅 9.2%，触发「单日涨幅 > 9% 不追」硬拦截，标签降为建议关注，未建仓。',
    actual: '拦截后两个交易日继续上行（假想收益 +8.9%），驱动是算力光模块订单上修，属于消息面新信息，不是单纯情绪拉升。',
    gap: '拦截只看涨了多少钱，没看为什么涨。有产业消息支撑、且仍在买入区里的强势票会被一刀切挡掉。',
    lesson: '拦不拦不该只问「今天涨了多少」，要同时问「有没有新的产业消息」和「还在不在买入区」。两个都满足时，涨得多不是拒绝理由。',
    sug: { kind: 'rule', title: '追高拦截在「有产业消息 + 仍在买入区」时降档为建议关注', ruleId: 'RC-1031',
      detail: '把单日涨幅硬拦截改成条件拦截：命中当日利多消息且现价 ≤ 买入区上沿时，不再直接拒绝，改为标签「建议关注」+ 提高止损。',
      impact: 'high', to: '规则审计 · 待确认' },
    src: { candidate: '2026-11-12', scoreId: 8791, planId: null },
    traces: [
      { time: '2026-11-12 09:41', title: '风控拦截', body: '涨幅 9.2% 超过追高容忍度，建仓申请被拒。', tone: 'warn' },
      { time: '2026-11-16 16:10', title: '影子复盘生成', body: '对未建仓标的做对照复盘：算出假想收益、定位拦截是否过严。', tone: 'info' },
      { time: '2026-11-16 16:11', title: 'AI 建议改规则', body: '指向现有规则 RC-1031 追高容忍度，需要人工确认。', tone: 'warn' }
    ]
  },
  {
    id: 1042, code: '601012', name: '隆基绿能', batch: '2026-11-12', kind: 'real',
    entry: '2026-11-12', exit: '2026-11-16', hold: 2, entryPrice: 19.5, exitPrice: 18.4,
    pnl: -5.8, maxDD: -6.1, execOK: '止损偏晚', verdict: '逻辑未兑现', status: 'thinking', iter: 2,
    rejectReason: '样本只有两笔，先攒够再改（2026-11-13 你驳回）',
    plan: '行业拐点预期建仓，买入区 19.2–19.8；跌破支撑 18.4 止损。',
    actual: '建仓当天尾盘板块整体走弱，11-13 跌破 19.0 没有动作，11-16 摸到 18.4 才走，实际 -5.8%。',
    gap: '止损价写在计划里了，但触发后拖了约 40 分钟才执行；板块级利空出现时也没有先减一半仓。',
    lesson: '同一个板块一起跌的时候，个股支撑位靠不住。板块指数走弱就把个股止损提前，宁可少赚不要抗。',
    sug: { kind: 'experience', title: '板块与个股止损冲突时以板块为准',
      detail: '所在板块指数当日跌幅超过 1.5% 时，个股止损线自动上移到成本价 -2%，不等原支撑位。',
      impact: 'high', to: '经验库 · 待审核' },
    src: { candidate: '2026-11-12', scoreId: 8788, planId: 5098 },
    traces: [
      { time: '2026-11-16 14:40', title: '止损离场', body: '触及 18.4，成交均价 18.42，本笔亏损 -5.8%。', tone: 'err' },
      { time: '2026-11-16 15:05', title: 'AI 出结论', body: '判定执行偏差在止损时机，建议沉淀高影响经验。', tone: 'info' },
      { time: '2026-11-13 10:12', title: '第 1 轮建议被你驳回', body: '理由：样本只有两笔，先攒够再改。', tone: 'warn' },
      { time: '2026-11-16 15:06', title: 'AI 重新思考中', body: 'review_rethink 任务已排队，会带同板块更多样本再出一版建议。', tone: 'info' }
    ]
  },
  {
    id: 1041, code: '600893', name: '航发动力', batch: '2026-11-12', kind: 'real',
    entry: '2026-11-12', exit: '2026-11-16', hold: 2, entryPrice: 41.6, exitPrice: 43.3,
    pnl: 4.2, maxDD: -0.8, execOK: '按计划', verdict: '逻辑兑现', status: 'adopted', iter: 1,
    plan: '买入区 41–43 建仓，止损 39.5，压力 43.5 减半仓，交付节奏上调作为核心逻辑。',
    actual: '11-12 建仓 41.6，11-16 放量到 43.3 触发减半仓并清仓，+4.2%。',
    gap: '完全按计划。唯一可优化：第二根放量阳线出现时没有加仓，仓位偏小。',
    lesson: '交付/订单这类产业数据上调的票，第二根放量阳线是可以加仓的信号，而不只是持有信号。',
    sug: { kind: 'experience', title: '产业数据上调的票，第二根放量阳线可加仓', expId: 'EXP-0012',
      detail: '连续两根放量阳线且量能高于首日，允许把仓位从计划值加到上限，前提是不突破单股仓位上限规则。',
      impact: 'normal', to: '经验库 · 已生效' },
    src: { candidate: '2026-11-12', scoreId: 8785, planId: 5096 },
    traces: [
      { time: '2026-11-16 15:02', title: 'AI 出结论', body: '判定逻辑兑现，建议沉淀加仓信号。', tone: 'info' },
      { time: '2026-11-16 18:20', title: '你采纳建议', body: '写入留痕，经验 EXP-0012 已审核生效。', tone: 'ok' }
    ]
  },
  {
    id: 1037, code: '000725', name: '京东方A', batch: '2026-11-11', kind: 'real',
    entry: '2026-11-10', exit: '2026-11-12', hold: 2, entryPrice: 4.12, exitPrice: 4.04,
    pnl: -1.9, maxDD: -2.4, execOK: '计划外操作', verdict: '半路下车', status: 'pending', iter: 1,
    plan: '箱体下沿 4.05 附近建仓，止损 3.98，上沿 4.35 减仓。',
    actual: '11-12 缩量回踩 4.06，人工手动卖出 4.04；随后 11-13 反弹到 4.28，没吃到。',
    gap: '卖出既没到止损也没到减仓位，属于盘中情绪操作，计划里完全没有这一条。',
    lesson: '计划外的手动卖出必须当场写原因。不然复盘里全是「卖飞」，但没人知道当时为什么卖。',
    sug: { kind: 'rule', title: '非计划卖出强制填写原因并计入执行偏差', ruleId: 'RC-1049',
      detail: '卖出价与计划档位不匹配时，交易前弹窗要求填原因（可跳过但留痕），并把该笔标记为计划外操作参与统计。',
      impact: 'high', to: '规则审计 · 待确认' },
    src: { candidate: '2026-11-11', scoreId: 8760, planId: 5072 },
    traces: [
      { time: '2026-11-12 13:26', title: '人工手动卖出', body: '4.04 全部卖出，未填原因。', tone: 'warn' },
      { time: '2026-11-13 09:10', title: 'AI 出结论', body: '标记为计划外操作，建议改流程而不是改策略。', tone: 'info' }
    ]
  },
  {
    id: 1033, code: '002049', name: '紫光国微', batch: '2026-11-10', kind: 'real',
    entry: '2026-11-09', exit: '2026-11-13', hold: 4, entryPrice: 79.0, exitPrice: 76.8,
    pnl: -2.8, maxDD: -4.1, execOK: '按计划', verdict: '板块退潮', status: 'adopted', iter: 1,
    plan: '买入区 78–80 建仓，止损 75.8。',
    actual: '11-12 起板块连续退潮，11-13 缩量跌破 77 按计划离场 -2.8%。',
    gap: '单笔执行没问题，但退潮第一天是尾盘跳水，隔夜仓位本身放大了回撤。',
    lesson: '题材退潮期不要隔夜：第一天出现长上影 + 尾盘跳水，次日大概率低开。',
    sug: { kind: 'experience', title: '题材退潮首日不隔夜', expId: 'EXP-0009',
      detail: '板块出现长上影且尾盘跳水时，次日开盘前把该板块持仓降到底仓，不等个股止损位。',
      impact: 'normal', to: '经验库 · 已生效' },
    src: { candidate: '2026-11-10', scoreId: 8712, planId: 5041 },
    traces: [
      { time: '2026-11-13 14:50', title: '按计划离场', body: '跌破 77，卖出 76.8。', tone: 'info' },
      { time: '2026-11-16 09:30', title: '你采纳建议', body: '经验 EXP-0009 生效。', tone: 'ok' }
    ]
  },
  {
    id: 1032, code: '600893', name: '航发动力', batch: '2026-11-10', kind: 'real',
    entry: '2026-11-06', exit: '2026-11-13', hold: 5, entryPrice: 40.9, exitPrice: 41.4,
    pnl: 1.1, maxDD: -1.9, execOK: '按计划', verdict: '基本持平', status: 'na', iter: 0,
    plan: '买入区 41–43 建仓，止损 39.5。',
    actual: '横盘 5 天，11-13 到期按计划离场，+1.1%。',
    gap: '没有偏差，也没有可推广的规律：这笔只是普通震荡，样本不支持任何结论。',
    lesson: '',
    sug: null,
    src: { candidate: '2026-11-10', scoreId: 8710, planId: 5040 },
    traces: [
      { time: '2026-11-13 15:10', title: 'AI 出结论', body: '判定个案，不产出通用建议，直接归档。', tone: 'ok' }
    ]
  },
  {
    id: 1031, code: '601012', name: '隆基绿能', batch: '2026-11-06', kind: 'real',
    entry: '2026-11-06', exit: '2026-11-13', hold: 5, entryPrice: 19.8, exitPrice: 18.5,
    pnl: -6.4, maxDD: -7.2, execOK: '止损偏晚', verdict: '左侧抄底失败', status: 'adopted', iter: 1,
    plan: '板块超跌反弹预期，买入区 19.2–19.8 建仓，止损 18.4。',
    actual: '建仓后板块继续下杀，11-13 破位离场 -6.4%。',
    gap: '选股时没看板块指数位置，板块在 20 日均线下方还做左侧抄底。',
    lesson: '板块指数在 20 日均线下方时不做左侧抄底，等站回均线再评估，哪怕错过第一根阳线。',
    sug: { kind: 'rule', title: '板块 20 日均线下方禁止左侧建仓', ruleId: 'RC-1038',
      detail: '建仓前置校验：所属板块指数收盘 < MA20 时，左侧标签（超跌/反弹）标的直接降为观察，不生成建仓方案。',
      impact: 'high', to: '规则审计 · 已生效' },
    src: { candidate: '2026-11-06', scoreId: 8705, planId: 5036 },
    traces: [
      { time: '2026-11-13 15:20', title: 'AI 出结论', body: '定位到板块位置校验缺失，建议改规则。', tone: 'info' },
      { time: '2026-11-16 10:02', title: '你采纳建议', body: '生成规则建议 RC-1038，走审计后生效。', tone: 'ok' }
    ]
  }
];

function reviewById(id) { return REVIEW_ROWS.find((r) => r.id === Number(id)) || null; }
function rvStatePill(status) { const m = RV_STATUS[status] || RV_STATUS.na; return '<span class="state ' + m.tone + '">' + m.label + '</span>'; }
function rvPnl(p) { return '<span class="mono ' + (p >= 0 ? 'wo-up' : 'wo-down') + '">' + (p >= 0 ? '+' : '') + p.toFixed(1) + '%</span>'; }

function filteredReviews() {
  return REVIEW_ROWS.filter((r) => {
    if (state.rvBatch && r.batch !== state.rvBatch) return false;
    if (state.rvFilter === 'pending') return r.status === 'pending';
    if (state.rvFilter === 'done') return r.status === 'adopted' || r.status === 'na' || r.status === 'rejected';
    return true;
  });
}

function rvRowHtml(r) {
  const active = state.rvId === r.id;
  const todo = r.status === 'pending' && !!r.sug;
  const acts = todo && state.rvRejectIn !== r.id
    ? '<span class="rq-acts">' + rqBtn('rvq-adopt', 'rv', r.id, '采纳', true) + rqBtn('rvq-reject', 'rv', r.id, '驳回') + '</span>'
    : '';
  return '<div class="cp-row rv-row' + (active ? ' active' : '') + '" role="button" tabindex="0" data-action="rv-select" data-rv="' + r.id + '">' +
    '<div class="cp-row-top">' +
      '<span class="cp-name">' + esc(r.name) + ' <span class="mono dim">' + r.code + '</span></span>' +
      (r.kind === 'shadow' ? tag('影子', 'gold') : '') +
      '<span class="spacer"></span>' + rvPnl(r.pnl) +
    '</div>' +
    '<div class="cp-row-reason">' + esc(r.verdict) + ' · ' + esc(r.execOK) + '</div>' +
    '<div class="cp-row-foot">' +
      '<span class="mono dim">' + esc(r.exit) + '</span>' +
      '<span class="dim">持 ' + r.hold + ' 日</span>' +
      (r.sug ? (r.sug.kind === 'rule' ? tag('建议改规则', 'blue') : tag('建议沉淀经验', 'outline')) : tag('个案', 'mute')) +
      '<span class="spacer"></span>' + rvStatePill(r.status) + acts +
    '</div>' +
    (todo && state.rvRejectIn === r.id ? rqRejectHtml('rvq', 'rv', r.id, '为什么这条不采纳？写一句，AI 下一轮得绕开它') : '') +
  '</div>';
}

function rvResultTab(r) {
  const shadow = r.kind === 'shadow';
  return '<dl class="kv">' +
    '<dt>' + (shadow ? '拦截后跟踪至' : '离场日') + '</dt><dd class="mono">' + esc(r.exit) + '</dd>' +
    '<dt>建仓价 / 卖出价</dt><dd class="mono">' + (r.entryPrice == null ? '<span class="dim">未建仓</span>' : r.entryPrice.toFixed(2) + ' → ' + r.exitPrice.toFixed(2)) + '</dd>' +
    '<dt>盈亏</dt><dd>' + rvPnl(r.pnl) + ' <span class="hint">' + (shadow ? '假想收益（对照，不进真实盈亏统计）' : '持仓 ' + r.hold + ' 个交易日 · 期间最大浮亏 ' + (r.maxDD == null ? '—' : r.maxDD.toFixed(1) + '%')) + '</span></dd>' +
    '<dt>' + (shadow ? '当时动作' : '是否按计划') + '</dt><dd>' + (r.execOK === '按计划' ? tag(r.execOK, 'green') : r.execOK === '被拦截' ? tag('拦截未建仓', 'gold') : tag(r.execOK, 'red')) + '</dd>' +
    '<dt>裁决</dt><dd>' + esc(r.verdict) + '</dd>' +
    '<dt>来源批次</dt><dd><button class="btn link xs" data-nav="#/candidates?date=' + r.batch + '">' + esc(r.batch) + ' 候选池 ' + icon('arrow', 'sm') + '</button></dd>' +
    '<dt>来源链路</dt><dd class="mono dim">candidate ' + esc(r.batch) + ' · score #' + r.src.scoreId + (r.src.planId ? ' · plan #' + r.src.planId : ' · 无建仓方案') + '</dd>' +
  '</dl>' +
  (shadow ? '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>影子复盘专门回答「当时拦住的那只票后来对不对」。它没有真实成交，只用来校准拦截规则，不会污染盈亏统计。</div></div>' : '');
}

function rvConclusionTab(r) {
  return '<div class="rv-cmp">' +
    '<div class="rv-cmp-col"><div class="cp-list-title">当初计划</div><div class="rv-cmp-txt">' + esc(r.plan) + '</div></div>' +
    '<div class="rv-cmp-col"><div class="cp-list-title">实际发生</div><div class="rv-cmp-txt">' + esc(r.actual) + '</div></div>' +
  '</div>' +
  '<div class="rv-gap">' + icon('alert') + '<div><b>偏差在哪：</b>' + esc(r.gap) + '</div></div>' +
  (r.lesson ? '<div class="rv-lesson"><div class="cp-list-title">一句话教训</div><div>' + esc(r.lesson) + '</div></div>'
    : '<div class="wo-empty">这笔没有可推广的规律，系统没有硬凑结论。</div>');
}

function rvSuggestTab(r) {
  if (!r.sug) {
    return '<div class="cp-scene-empty">AI 判断这是个案，没有产出要采纳的建议。复盘允许「没有结论」——硬总结出来的规律比没有规律更贵。</div>';
  }
  const s = r.sug;
  const head = '<div class="rv-sug">' +
    '<div class="rv-sug-head">' + (s.kind === 'rule' ? tag('改规则', 'blue') : tag('沉淀经验', 'outline')) +
      (s.impact === 'high' ? tag('高影响', 'gold') : '') +
      '<b>' + esc(s.title) + '</b></div>' +
    '<div class="rv-sug-txt">' + esc(s.detail) + '</div>' +
    '<dl class="kv">' +
      '<dt>采纳之后</dt><dd>' + esc(s.to) + (s.kind === 'rule' && s.ruleId ? '（对应规则 <button class="btn link xs" data-nav="#/system/rules?bucket=all&id=' + s.ruleId + '">' + s.ruleId + ' ' + icon('arrow', 'sm') + '</button>）' : '') + (s.expId ? '（经验 <button class="btn link xs" data-nav="#/experience?id=' + s.expId + '">' + s.expId + ' ' + icon('arrow', 'sm') + '</button>）' : '') + '</dd>' +
      '<dt>不采纳</dt><dd>写一条原因，AI 会重新想一版建议；连续驳回不会重复推送同一条。</dd>' +
      '<dt>当前轮次</dt><dd>第 ' + r.iter + ' 版' + (r.rejectReason ? ' · ' + tag('上一轮驳回', 'gold') + ' ' + esc(r.rejectReason) : '') + '</dd>' +
    '</dl>' +
  '</div>';
  if (r.status === 'pending') {
    let acts = '';
    if (state.rvConfirm === 'adopt-' + r.id) {
      acts = '<div class="inline-confirm">' +
        '<div class="ic-title">确认采纳这条建议？</div>' +
        '<div class="ic-desc">' + (s.kind === 'rule'
          ? '采纳 = 生成一条规则建议并进入 AI 审计，审计通过后还需要你在规则建议里再确认一次才会生效。这一步不会直接改交易行为。'
          : '采纳 = 写入经验库并进入待审核队列，审核通过后才注入到相关 Agent 的提示词里，不会立刻影响下单。') + '</div>' +
        '<div class="ic-actions"><button class="btn sm" data-action="rv-cancel">取消</button>' +
          '<button class="btn primary sm" data-action="rv-adopt-ok" data-rv="' + r.id + '">确认采纳</button></div></div>';
    } else if (state.rvConfirm === 'reject-' + r.id) {
      acts = '<div class="inline-confirm danger">' +
        '<div class="ic-title">驳回并让 AI 重新思考</div>' +
        '<div class="ic-desc">原因必填，AI 会带着这条原因重新出建议；原因本身也会留档，是你和系统争论过的证据。</div>' +
        '<textarea class="input" id="rv-reason" rows="3" placeholder="例如：样本太少，先攒到 10 笔再说"></textarea>' +
        '<div class="ic-actions"><button class="btn sm" data-action="rv-cancel">取消</button>' +
          '<button class="btn danger sm" data-action="rv-reject-ok" data-rv="' + r.id + '">提交驳回</button></div></div>';
    } else {
      acts = '<div class="rv-acts top"><button class="btn primary sm" data-action="rv-adopt" data-rv="' + r.id + '">采纳建议</button>' +
        '<button class="btn sm" data-action="rv-reject" data-rv="' + r.id + '">驳回</button>' +
        '<span class="hint">这一笔只有这里需要你动手。</span></div>';
    }
    return acts + head + '<div class="cap-note" style="margin-top:12px">' + icon('info') +
      '<div>这条建议同时会进 <button class="btn link xs" data-nav="#/reviews?board=sug">闭环建议队列 ' + icon('arrow', 'sm') + '</button>，那里能看到 AI 辩证审核的结论和反对意见。</div></div>';
  }
  if (r.status === 'thinking') {
    return head + '<div class="cap-note accent">' + icon('rotate', 'sm') + '<div>重思考中：驳回已提交，AI 正在补样本重出一版建议，出新建议时会在复盘队列里提示你。</div></div>';
  }
  return head + '<div class="cap-note">' + icon('check') + '<div>已采纳（第 ' + r.iter + ' 版）。后续状态去 ' +
    (s.kind === 'rule'
      ? '<button class="btn link xs" data-nav="#/system/rules?bucket=all&id=' + (s.ruleId || '') + '">规则审计看</button>'
      : '<button class="btn link xs" data-nav="#/experience?id=' + (s.expId || '') + '">经验库看</button>') + '。</div></div>';
}

function rvTraceTab(r) {
  return '<div class="timeline">' + r.traces.map((t) =>
    '<div class="tl-item"><span class="tl-dot ' + (t.tone || 'info') + '"></span>' +
    '<div class="tl-head"><span class="tl-title">' + esc(t.title) + '</span><span class="tl-time">' + esc(t.time) + '</span></div>' +
    '<div class="tl-body">' + esc(t.body) + '</div></div>').join('') + '</div>';
}

function reviewDetailHtml(r) {
  const tabs = [['result', '结果'], ['concl', 'AI 结论'], ['sug', '建议'], ['trace', '留痕']];
  const body = state.rvTab === 'concl' ? rvConclusionTab(r)
    : state.rvTab === 'sug' ? rvSuggestTab(r)
    : state.rvTab === 'trace' ? rvTraceTab(r) : rvResultTab(r);
  const jump = r.status === 'pending' && state.rvTab !== 'sug'
    ? '<div class="rv-jump">' + icon('alert', 'sm') + '<span>这笔有 1 条建议等你裁决</span>' +
      '<button class="btn primary xs" data-action="rv-tab-jump" data-tab="sug">去裁决 ' + icon('arrow', 'sm') + '</button></div>' : '';
  return '<div class="card">' +
    '<div class="detail-head">' +
      '<div style="min-width:0">' +
        '<div class="detail-title">' + esc(r.name) + ' <span class="mono dim">' + r.code + '</span> ' +
          (r.kind === 'shadow' ? tag('影子复盘 · 未实际建仓', 'gold') : tag('真实复盘', 'outline')) + '</div>' +
        '<div class="detail-sub">复盘 #' + r.id + ' · 离场 ' + esc(r.exit) + ' · 持仓 ' + r.hold + ' 日 · 来源批次 ' + esc(r.batch) + '</div>' +
        '<div class="detail-tags">' + (r.pnl >= 0 ? tag('+' + r.pnl.toFixed(1) + '%', 'red') : tag(r.pnl.toFixed(1) + '%', 'green')) + ' ' + tag(r.verdict, r.pnl >= 0 ? 'green' : 'mute') + ' ' + rvStatePill(r.status) + '</div>' +
      '</div>' +
      '<div class="spacer"></div>' +
      '<div class="cp-acts">' +
        '<button class="btn sm" data-action="rv-kline" data-rv="' + r.id + '">' + icon('chart', 'sm') + '看K线</button>' +
        '<div class="cp-ext">' + quoteUrls(r.code).map((q) => '<a class="btn link xs" href="' + q.url + '" target="_blank" rel="noopener noreferrer">' + esc(q.name) + ' ' + icon('external', 'sm') + '</a>').join('') + '</div>' +
      '</div>' +
    '</div>' +
    '<div class="detail-tabs">' + tabs.map((t) =>
      '<button class="detail-tab ' + (state.rvTab === t[0] ? 'active' : '') + '" data-action="rv-tab" data-tab="' + t[0] + '">' + t[1] +
      (t[0] === 'sug' && r.status === 'pending' && r.sug ? ' ' + tag('待裁决', 'gold') : '') + '</button>').join('') + '</div>' +
    '<div class="cp-tab-body">' + jump + body + '</div>' +
  '</div>';
}

function rvBoardList() {
  const list = filteredReviews();
  const sel = list.find((r) => r.id === state.rvId) || list[0] || reviewById(state.rvId) || REVIEW_ROWS[0];
  state.rvId = sel.id;
  const pend = REVIEW_ROWS.filter((r) => r.status === 'pending').length;
  const done = REVIEW_ROWS.filter((r) => r.status === 'adopted').length;
  const toExp = REVIEW_ROWS.filter((r) => r.status === 'adopted' && r.sug && r.sug.kind === 'experience').length;
  const stats = [
    { label: '待你裁决', value: pend, sub: '只看建议，不用读全文', tone: pend ? 'warn' : '' },
    { label: '近 30 日复盘', value: REVIEW_ROWS.length, sub: '含影子复盘', tone: '' },
    { label: '建议采纳', value: done, sub: '其余驳回或个案' },
    { label: '已转经验', value: toExp, sub: '进入经验库', tone: 'info' }
  ];
  const filters = [['', '全部'], ['pending', '待你裁决'], ['done', '已处理']];
  return '<div class="cp-toolbar">' +
      '<div class="cp-chips">' + filters.map((f) =>
        '<button class="cp-chip ' + (state.rvFilter === f[0] ? 'active' : '') + '" data-action="rv-filter" data-f="' + f[0] + '">' + f[1] + '</button>').join('') + '</div>' +
      (state.rvBatch ? '<button class="btn xs" data-action="rv-clear-batch">' + esc(state.rvBatch) + ' 批次 · 清除 ' + icon('x', 'sm') + '</button>' : '') +
      '<span class="hint">每笔离场自动出一份，人工卖出也会触发；这里只管单笔。</span>' +
    '</div>' +
    '<div class="metric-strip q4" style="margin-bottom:14px">' + stats.map((s) =>
      '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div><div class="metric-value ' + (s.tone || '') + '">' + esc(s.value) + '</div><div class="metric-sub">' + esc(s.sub) + '</div></div>').join('') + '</div>' +
    '<div class="cp-layout">' +
      '<div class="card cp-list-card">' + rqBarHtml(REVIEW_ROWS.filter((r) => r.status === 'pending' && r.sug).length) + '<div class="cp-list" id="rv-list">' + (list.length ? list.map(rvRowHtml).join('') : '<div class="wo-empty" style="padding:14px">当前筛选下没有复盘。</div>') + '</div></div>' +
      '<div class="cp-detail" id="rv-detail">' + reviewDetailHtml(sel) + '</div>' +
    '</div>' +
    '<div class="cap-note" style="margin-top:14px">' + icon('info') + '<div>这一页只看单笔。整段时间赚在哪、AI 选得准不准、建议审核到哪一步，在上面其他看板里；一笔复盘产出的建议不会立刻改系统行为，它要进闭环建议队列过 AI 辩证审核。</div></div>';
}

function renderReviews() {
  const head = '<div class="subhead">' +
      '<div><h2>交易复盘</h2><p>五个看板是同一条链的不同切面：一笔怎么看 → 整体赚亏 → 选得准不准 → 建议有没有落地 → 规律能不能量化。</p></div>' +
      '<div class="spacer"></div>' +
      '<button class="btn xs" data-nav="#/experience">经验沉淀 ' + icon('arrow', 'sm') + '</button>' +
      '<button class="btn xs" data-nav="#/system/rules">规则审计 ' + icon('arrow', 'sm') + '</button>' +
    '</div>' + rvBoardBar();
  if (state.rvBoard === 'attr') return head + rvBoardAttr();
  if (state.rvBoard === 'track') return head + rvBoardTrack();
  if (state.rvBoard === 'sug') return head + rvBoardSug();
  if (state.rvBoard === 'factor') return head + rvBoardFactor();
  return head + rvBoardList();
}

function refreshRvDetail() {
  const box = $('#rv-detail');
  const r = reviewById(state.rvId);
  if (box && r) { box.innerHTML = reviewDetailHtml(r); hydrateIcons(box); }
}

function refreshExpDetail() {
  const box = $('#exp-detail');
  const e = expById(state.expId);
  if (box && e) { box.innerHTML = expDetailHtml(e); hydrateIcons(box); }
}

function selectReview(id) {
  const r = reviewById(id);
  if (!r) return;
  state.rvId = r.id;
  state.rvConfirm = null;
  $$('.rv-row').forEach((el) => el.classList.toggle('active', Number(el.dataset.rv) === r.id));
  const box = $('#rv-detail');
  if (box) { box.innerHTML = reviewDetailHtml(r); hydrateIcons(box); }
  syncRvHash();
}

function syncRvHash() {
  if (state.route !== '#/reviews') return;
  let next;
  if (state.rvBoard === 'sug') next = '#/reviews?board=sug&sgs=' + state.sgsId;
  else if (state.rvBoard === 'track') next = '#/reviews?board=track&track=' + state.rvTrackDate;
  else if (state.rvBoard !== 'list') next = '#/reviews?board=' + state.rvBoard;
  else next = '#/reviews?id=' + state.rvId + (state.rvBatch ? '&date=' + state.rvBatch : '');
  if (location.hash !== next) history.replaceState(null, '', next);
}

function applyRvAdopt(r) {
  r.status = 'adopted';
  r.traces.unshift({ time: '刚刚', title: '你采纳建议', body: r.sug.kind === 'rule' ? '生成规则建议，进入 AI 审计（不直接生效）。' : '写入经验库，进入待审核队列。', tone: 'ok' });
}

function applyRvReject(r, reason) {
  r.status = 'thinking';
  r.iter += 1;
  r.rejectReason = reason + '（刚刚你驳回）';
  r.traces.unshift({ time: '刚刚', title: '第 ' + r.iter + ' 轮建议被你驳回', body: '理由：' + reason + '。已提交 review_rethink 任务，AI 重思考中。', tone: 'warn' });
}

function adoptReview(id) {
  const r = reviewById(id);
  if (!r) return;
  applyRvAdopt(r);
  if (state.rvFilter === 'pending') state.rvFilter = '';
  renderView();
  renderReviewsToast(r);
}

function renderReviewsToast(r) {
  const s = r.sug;
  toast('建议已采纳', s.kind === 'rule'
    ? '规则建议已生成，去规则审计确认才会生效'
    : '已写入经验库待审核，审核通过才注入 Agent', 'ok',
    { label: s.kind === 'rule' ? '去规则审计' : '去经验库', fn: () => { location.hash = s.kind === 'rule' ? '#/system/rules' : '#/experience'; } });
}

function rejectReview(id) {
  const r = reviewById(id);
  const el = $('#rv-reason');
  const reason = el ? (el.value || '').trim() : '';
  if (!r) return;
  if (!reason) { if (el) { el.focus(); toast('需要写原因', '驳回必须告诉 AI 为什么，不然它只会重出一版一样的。', 'warn'); } return; }
  applyRvReject(r, reason);
  state.rvConfirm = null;
  if (state.rvFilter === 'pending') state.rvFilter = '';
  renderView();
  toast('已驳回', 'AI 正在重新思考这条建议，出新版本时会在复盘队列提示你。', 'info');
}

/* ---------- 就地裁决：列表行上直接采纳/驳回，处理完自动跳下一条 ---------- */
function nextPending(rows, decidedId, isTodo) {
  const n = rows.length;
  if (!n) return null;
  const from = rows.findIndex((r) => String(r.id) === String(decidedId));
  for (let k = 1; k <= n; k += 1) {
    const cand = rows[(from + k + n) % n];
    if (cand && isTodo(cand)) return cand;
  }
  return null;
}

function quickRowEl(item) {
  const id = String(item.id);
  return document.querySelector('.rv-row[data-rv="' + id + '"], .sgs-row[data-sgs="' + id + '"], .ex-row[data-exp="' + id + '"]');
}

function quickDone(rows, item, o) {
  const rest = rows.filter(o.isTodo).length;
  const next = rest ? nextPending(rows, item.id, o.isTodo) : null;
  renderView();
  if (next) {
    o.select(next.id);
    const el = quickRowEl(next);
    if (el) el.scrollIntoView({ block: 'nearest' });
  }
  toast(o.title, o.body + (next
    ? ' · 还剩 ' + rest + ' 条，已跳到「' + o.label(next) + '」'
    : ' · 这个队列没有等你裁决的了'), o.kind || 'ok', o.undo
    ? {
      label: '撤销',
      fn: () => {
        o.undo();
        renderView();
        o.select(item.id);
        const el = quickRowEl(item);
        if (el) el.scrollIntoView({ block: 'nearest' });
        toast('已撤销', '「' + o.label(item) + '」回到待你裁决，留痕也清掉了。', 'info');
      }
    }
    : null);
}

function rqBarHtml(n) {
  return '<div class="rq-bar">' + (n
    ? '<b>等你裁决 ' + n + ' 条</b><span class="dim">行上直接点「采纳 / 驳回」，处理完自动跳下一条，不用进详情</span>'
    : '<span class="dim">这个队列没有等你裁决的条目</span>') + '</div>';
}

function rqBtn(action, idAttr, id, label, pri) {
  return '<button class="btn xs' + (pri ? ' primary' : '') + '" data-action="' + action + '" data-' + idAttr + '="' + id + '">' + esc(label) + '</button>';
}

function rqRejectHtml(scope, idAttr, id, ph) {
  return '<div class="rq-reject" data-action="' + scope + '-reject-keep">' +
    '<textarea class="input" id="' + scope + '-reason" rows="2" placeholder="' + ph + '"></textarea>' +
    '<div class="rq-reject-acts">' +
      '<button class="btn xs primary" data-action="' + scope + '-reject-ok" data-' + idAttr + '="' + id + '">确认驳回</button>' +
      '<button class="btn xs" data-action="' + scope + '-reject-cancel">取消</button>' +
      '<span class="hint">理由会写进留痕，AI 下一轮得绕开它</span>' +
    '</div>' +
  '</div>';
}

function openInlineReject(scope, id) {
  state[scope + 'RejectIn'] = id;
  state[scope === 'rv' ? 'rvConfirm' : scope === 'sgs' ? 'sgsConfirm' : 'expConfirm'] = null;
  if (scope === 'sgs') state.sgsQuickConfirm = null;
  if (scope === 'exp') state.expQuickConfirm = null;
  renderView();
  const ta = $('#' + scope + 'q-reason');
  if (ta) { ta.focus(); ta.scrollIntoView({ block: 'nearest' }); }
}

function closeInlineReject(scope) {
  state[scope + 'RejectIn'] = null;
  renderView();
}

function inlineRejectReason(scopeId, label) {
  const el = $('#' + scopeId);
  const reason = el ? (el.value || '').trim() : '';
  if (!reason) {
    if (el) { el.focus(); toast('需要写理由', label, 'warn'); }
    return null;
  }
  return reason;
}

function rvQuickAdopt(id) {
  const r = reviewById(id);
  if (!r) return;
  const snap = r.status;
  applyRvAdopt(r);
  state.rvRejectIn = null;
  quickDone(filteredReviews(), r, {
    isTodo: (x) => x.status === 'pending' && !!x.sug,
    label: (x) => x.name,
    select: selectReview,
    title: '已采纳建议',
    body: r.sug.kind === 'rule' ? '规则建议已生成，还要在规则审计确认才生效' : '已写入经验库，等你审核才注入 Agent',
    undo: () => { r.status = snap; r.traces.shift(); }
  });
}

function rvQuickReject(id) {
  const r = reviewById(id);
  if (!r) return;
  const reason = inlineRejectReason('rvq-reason', '驳回要写一句为什么，不然 AI 只会换个说法再提一遍。');
  if (!reason) return;
  const snap = { status: r.status, iter: r.iter, why: r.rejectReason };
  applyRvReject(r, reason);
  state.rvRejectIn = null;
  quickDone(filteredReviews(), r, {
    isTodo: (x) => x.status === 'pending' && !!x.sug,
    label: (x) => x.name,
    select: selectReview,
    title: '已驳回',
    body: 'AI 重思考中，出新版本会回到这条队列',
    kind: 'warn',
    undo: () => { r.status = snap.status; r.iter = snap.iter; r.rejectReason = snap.why; r.traces.shift(); }
  });
}

function sgsQuickAdopt(id) {
  const s = sugById(id);
  if (!s) return;
  if (s.kind === 'hard' && state.sgsQuickConfirm !== s.id) {
    state.sgsQuickConfirm = s.id;
    state.sgsRejectIn = null;
    renderView();
    return;
  }
  const snap = { status: s.status, eff: s.effectiveWhen };
  applySugAdopt(s);
  state.sgsQuickConfirm = null;
  state.sgsRejectIn = null;
  quickDone(filteredSugs(), s, {
    isTodo: (x) => x.status === 'pending',
    label: (x) => x.title,
    select: selectSug,
    title: '已采纳',
    body: s.kind === 'hard' ? '写入生效规则表，下一个交易日开始约束 Agent' : '已写入偏好/提示词，只改变给你的建议口径',
    undo: () => { s.status = snap.status; s.effectiveWhen = snap.eff; s.traces.shift(); }
  });
}

function sgsQuickReject(id) {
  const s = sugById(id);
  if (!s) return;
  const reason = inlineRejectReason('sgsq-reason', '不写理由，AI 只会换个说法再提一遍。');
  if (!reason) return;
  const snap = { status: s.status, why: s.rejectReason };
  applySugReject(s, reason);
  state.sgsQuickConfirm = null;
  state.sgsRejectIn = null;
  quickDone(filteredSugs(), s, {
    isTodo: (x) => x.status === 'pending',
    label: (x) => x.title,
    select: selectSug,
    title: '已驳回',
    body: '理由已留痕，这条不再重复推送',
    kind: 'warn',
    undo: () => { s.status = snap.status; s.rejectReason = snap.why; s.traces.shift(); }
  });
}

function sgsQuickAudit(id) {
  const s = sugById(id);
  if (!s) return;
  const snap = { audit: s.audit, reason: s.auditReason };
  s.audit = 'pass';
  s.auditMode = 'ai';
  s.auditReason = '审核完成：样本 ' + s.evidence.count + ' 笔，方向与既有目标不冲突，属于低代价改动。（原型里这条结论是示意）';
  s.traces.unshift({ time: '刚刚', title: 'AI 辩证审核通过', body: s.auditReason, tone: 'ok' });
  quickDone(filteredSugs(), s, {
    isTodo: (x) => x.status === 'pending',
    label: (x) => x.title,
    select: selectSug,
    title: 'AI 审核完成',
    body: '结论是通过，行上「采纳」才生效',
    kind: 'info',
    undo: () => { s.audit = snap.audit; s.auditReason = snap.reason; s.traces.shift(); }
  });
}

function expQuickApprove(id) {
  const e = expById(id);
  if (!e) return;
  if (e.impact === 'high' && state.expQuickConfirm !== e.id) {
    state.expQuickConfirm = e.id;
    state.expRejectIn = null;
    renderView();
    return;
  }
  const snap = { status: e.status, agents: e.agents.slice() };
  applyExpApprove(e);
  state.expQuickConfirm = null;
  state.expRejectIn = null;
  quickDone(filteredExperiences(), e, {
    isTodo: (x) => x.status === 'pending_review',
    label: (x) => x.title,
    select: selectExp,
    title: e.impact === 'high' ? '已生效，同时送去规则审计' : '已生效',
    body: e.impact === 'high' ? '高影响经验不直接改交易参数，规则确认后才落地' : 'Agent 现在检索得到这条判断了',
    undo: () => { e.status = snap.status; e.agents = snap.agents; e.logs.shift(); }
  });
}

function expQuickReject(id) {
  const e = expById(id);
  if (!e) return;
  const reason = inlineRejectReason('expq-reason', '驳回要告诉 AI 为什么，不然是给它留了个再来一次的口子。');
  if (!reason) return;
  const snap = { status: e.status, agents: e.agents.slice() };
  applyExpReject(e, reason);
  state.expQuickConfirm = null;
  state.expRejectIn = null;
  quickDone(filteredExperiences(), e, {
    isTodo: (x) => x.status === 'pending_review',
    label: (x) => x.title,
    select: selectExp,
    title: '已驳回',
    body: '不会注入 Agent，同主题不再重复推送',
    kind: 'warn',
    undo: () => { e.status = snap.status; e.agents = snap.agents; e.logs.shift(); }
  });
}

/* ---------- 闭环建议的操作 ---------- */
function selectSug(id) {
  const s = sugById(id);
  if (!s) return;
  state.sgsId = s.id;
  state.sgsConfirm = null;
  $$('.sgs-row').forEach((el) => el.classList.toggle('active', Number(el.dataset.sgs) === s.id));
  const box = $('#sgs-detail');
  if (box) { box.innerHTML = sugDetailHtml(s); hydrateIcons(box); }
  syncRvHash();
}

function refreshSugDetail() {
  const box = $('#sgs-detail');
  const s = sugById(state.sgsId);
  if (box && s) { box.innerHTML = sugDetailHtml(s); hydrateIcons(box); }
}

function applySugAdopt(s) {
  s.status = 'adopted';
  s.effectiveWhen = '已于刚刚生效';
  s.traces.unshift({ time: '刚刚', title: s.kind === 'hard' ? '你二次确认，规则已生效' : '你确认采纳', body: s.writesTo + '。已留一条变更记录，可以从这里回滚。', tone: 'ok' });
}

function applySugReject(s, reason) {
  s.status = 'rejected';
  s.rejectReason = reason;
  s.traces.unshift({ time: '刚刚', title: '你驳回', body: '理由：' + reason + '。这条约束会写进记录，AI 下次提类似建议时会被拦一下。', tone: 'warn' });
}

function adoptSug(id) {
  const s = sugById(id);
  if (!s) return;
  applySugAdopt(s);
  state.sgsConfirm = null;
  if (state.sgsFilter === 'pending') state.sgsFilter = '';
  renderView();
  toast('建议已生效', s.kind === 'hard' ? '写入生效规则表，下一个交易日开始约束 Agent 行为' : '已写入偏好/提示词，只改变给你的建议口径', 'ok',
    { label: s.kind === 'hard' && s.ruleId ? '去规则审计' : '看处理记录', fn: () => { location.hash = s.kind === 'hard' && s.ruleId ? '#/system/rules?bucket=all&id=' + s.ruleId : '#/reviews?board=sug&sgs=' + s.id; } });
}

function rejectSug(id) {
  const s = sugById(id);
  const el = $('#sgs-reject-reason');
  const reason = el ? (el.value || '').trim() : '';
  if (!s) return;
  if (!reason) { if (el) { el.focus(); toast('需要写理由', '不写理由，AI 只会换个说法再提一遍。', 'warn'); } return; }
  applySugReject(s, reason);
  state.sgsConfirm = null;
  if (state.sgsFilter === 'pending') state.sgsFilter = '';
  renderView();
  toast('已驳回', '理由已留痕，这条建议不再重复推送。', 'warn');
}

function forceSug(id) {
  const s = sugById(id);
  const el = $('#sgs-force-reason');
  const reason = el ? (el.value || '').trim() : '';
  if (!s) return;
  if (!reason) { if (el) { el.focus(); toast('强制采纳也要理由', 'AI 已经说了不通过，你 override 它得留下是谁拍的板。', 'warn'); } return; }
  s.status = 'adopted';
  s.conflictNote = reason + '（刚刚你强制采纳，AI 结论未通过）';
  s.effectiveWhen = '已于刚刚生效（强制采纳）';
  s.traces.unshift({ time: '刚刚', title: '你强制采纳（AI 未通过）', body: '理由：' + reason + '。已写入 conflict_note，永久留痕。', tone: 'err' });
  state.sgsConfirm = null;
  if (state.sgsFilter === 'pending') state.sgsFilter = '';
  renderView();
  toast('已强制采纳', '生效了，但 AI 的反对意见和你的理由都留在记录里。', 'warn');
}

function reRaiseSug(id) {
  const s = sugById(id);
  if (!s) return;
  s.status = 'thinking';
  s.audit = 'pending';
  s.auditReason = '';
  s.traces.unshift({ time: '刚刚', title: '你让 AI 重出一版', body: 'AI 会带着自己的反对理由重新找样本，出新结论时排回待审队列。', tone: 'info' });
  state.sgsConfirm = null;
  if (state.sgsFilter === 'pending') state.sgsFilter = '';
  renderView();
  toast('已重新排队', 'AI 会带着反对理由重找样本，出新版本时提醒你。', 'info');
}

function auditSugNow(id) {
  const s = sugById(id);
  if (!s) return;
  s.audit = 'pass';
  s.auditMode = 'ai';
  s.auditReason = '审核完成：样本 ' + s.evidence.count + ' 笔，方向与既有目标不冲突，属于低代价改动。（原型里这条结论是示意）';
  s.traces.unshift({ time: '刚刚', title: 'AI 辩证审核通过', body: s.auditReason, tone: 'ok' });
  renderView();
  toast('AI 审核完成', '结论是通过，等你确认才生效。', 'ok');
}

function auditAllSugs() {
  const pend = SUG_ROWS.filter((s) => s.audit === 'pending');
  if (!pend.length) { toast('没有待审建议', '增量审核只处理还没跑过 AI 辩证审核的条目。', 'info'); return; }
  pend.forEach((s) => {
    s.audit = 'pass';
    s.auditReason = '批量审核完成：样本 ' + s.evidence.count + ' 笔，未发现与既有规则冲突。（原型里这条结论是示意）';
    s.traces.unshift({ time: '刚刚', title: 'AI 辩证审核通过', body: s.auditReason, tone: 'ok' });
  });
  renderView();
  toast('增量 AI 审核完成', pend.length + ' 条已出结论，通过的要你确认才生效。', 'ok');
}

function rollbackSug(id) {
  toast('回滚还没上线', '真实系统里这个按钮是禁用态（功能开发中）。这里保留它，是为了让「生效后能撤回」这件事在流程里看得见。', 'warn');
}

function proposeFactor(id) {
  const f = FC_ROWS.find((x) => x.id === id);
  if (!f) return;
  f.status = 'testing';
  f.verdict = '已提为因子建议，等规则审计二次确认；回测参数沿用当前样本窗口。';
  renderView();
  toast('已提为因子建议', '和规则走同一套确认流程，不会自己进评分。', 'ok',
    { label: '去规则审计', fn: () => { location.hash = '#/system/rules'; } });
}

/* ---------- 复盘看板：组合复盘 / 选股效果验证 / 闭环建议 / 候选因子 ---------- */
const RV_BOARDS = [
  ['list', '逐笔复盘'], ['attr', '组合复盘'], ['track', '选股效果验证'], ['sug', '闭环建议'], ['factor', '候选因子']
];
const RV_BOARD_NOTE = {
  list: '一笔一笔看：这笔赚没赚、是不是按计划做的、AI 的建议要不要采纳。',
  attr: '这段时间组合赚在哪、亏在哪、哪只在拖后腿——只看真实成交。',
  track: '回答「AI 选得准不准」：按选中日统计 T+3/T+5/T+10，跟你有没有建仓无关。',
  sug: '复盘产出的调整建议全量队列，先过 AI 辩证审核，再由你确认才会写进规则或偏好。',
  factor: '从复盘里归纳出的候选因子，先验证再谈上线；没验证过的因子不能变成规则。'
};

const PORT_RANGE = {
  label: '近 30 日', start: '2026-10-19', end: '2026-11-16',
  cumPct: 6.8, todayPct: 0.44, todayAmount: 5180, cost: 1126000, value: 1179300,
  unrealized: 53300, trades: 21, upDays: 18, downDays: 11,
  bestDay: { date: '2026-11-11', pct: 2.1, why: '两笔长持同时兑现，没有提前下车' },
  worstDay: { date: '2026-11-10', pct: -2.4, why: '隆基绿能左侧抄底失败，同一天 3 笔一起离场' },
  maxDD: { pct: -3.9, from: '2026-11-06', to: '2026-11-10' },
  shadow: 2
};

const PORT_DAILY = [
  { date: '2026-11-16', pct: 0.44, amount: 5180, note: '2 笔平仓，1 笔追高被拦截' },
  { date: '2026-11-13', pct: -0.86, amount: -9800, note: '紫光国微止盈提前，少赚一档' },
  { date: '2026-11-12', pct: 0.64, amount: 7200, note: '航发动力按计划持有' },
  { date: '2026-11-11', pct: 2.10, amount: 23400, note: '长持两笔同时兑现' },
  { date: '2026-11-10', pct: -2.40, amount: -27600, note: '一天 3 笔离场，抄底失败' },
  { date: '2026-11-09', pct: 1.32, amount: 15100, note: '本区间最赚钱的一天' },
  { date: '2026-11-06', pct: -0.31, amount: -3500, note: '新开 4 笔，正常波动' }
];

const PORT_HOLD = [
  { code: '600893', name: '航发动力', weight: 21, cost: 240000, value: 259920, pnlPct: 8.3, contrib: 2.4, advice: '继续持有，止盈线上移到 78.4', exec: '按计划', rvId: 1041 },
  { code: '002371', name: '北方华创', weight: 19, cost: 210000, value: 224910, pnlPct: 7.1, contrib: 1.9, advice: '到第一档止盈位，减 1/3', exec: '按计划', rvId: null },
  { code: '002463', name: '沪电股份', weight: 15, cost: 160000, value: 175360, pnlPct: 9.6, contrib: 1.7, advice: '浮盈超 8%，按纪律不许再加仓', exec: '按计划', rvId: null },
  { code: '688981', name: '中芯国际', weight: 16, cost: 180000, value: 187560, pnlPct: 4.2, contrib: 1.2, advice: '正常持有，等板块资金确认', exec: '按计划', rvId: null },
  { code: '002049', name: '紫光国微', weight: 13, cost: 146000, value: 151750, pnlPct: 3.9, contrib: 0.8, advice: '板块退潮信号已亮，反弹减半仓', exec: '提前止盈', rvId: 1033 },
  { code: '601012', name: '隆基绿能', weight: 16, cost: 190000, value: 181260, pnlPct: -4.6, contrib: -1.2, advice: '唯一亏损仓：跌破 23.1 无条件离场', exec: '未按计划', rvId: 1031 }
];

const PORT_CYCLE = [
  { label: '长持 ≥ 40 日', trades: 3, win: 0.67, avg: 6.4, cum: 19.2, verdict: '最稳的一档，收益主要来源' },
  { label: '波段 10–39 日', trades: 5, win: 0.60, avg: 3.1, cum: 15.4, verdict: '正常，按计划止盈的比例最高' },
  { label: '短线 4–9 日', trades: 7, win: 0.43, avg: 0.6, cum: 4.2, verdict: '一半以上靠运气，别再凭感觉做' },
  { label: '超短 ≤ 3 日', trades: 6, win: 0.17, avg: -2.4, cum: -14.6, verdict: '这档在稳定亏钱', sugId: 3018 }
];

const TRACK_ROWS = [
  { date: '2026-11-16', picked: 8, buyable: 3, opened: 0, n3: 0, h3: 0, n5: 0, h5: 0, n10: 0, h10: 0, avg5: null, excess: null, state: '未到期' },
  { date: '2026-11-13', picked: 7, buyable: 2, opened: 2, n3: 7, h3: 4, n5: 0, h5: 0, n10: 0, h10: 0, avg5: null, excess: null, state: '跟踪中' },
  { date: '2026-11-12', picked: 9, buyable: 4, opened: 3, n3: 9, h3: 6, n5: 9, h5: 6, n10: 0, h10: 0, avg5: 2.4, excess: 1.1, state: 'T+10 未到期' },
  { date: '2026-11-11', picked: 11, buyable: 5, opened: 4, n3: 11, h3: 8, n5: 11, h5: 8, n10: 9, h10: 6, avg5: 4.1, excess: 2.6, state: '基本结算' },
  { date: '2026-11-10', picked: 8, buyable: 3, opened: 3, n3: 8, h3: 3, n5: 8, h5: 3, n10: 8, h10: 2, avg5: -2.2, excess: -3.4, state: '已结算' },
  { date: '2026-11-09', picked: 6, buyable: 2, opened: 1, n3: 6, h3: 4, n5: 6, h5: 5, n10: 6, h10: 4, avg5: 5.6, excess: 3.2, state: '已结算' },
  { date: '2026-11-06', picked: 10, buyable: 4, opened: 4, n3: 10, h3: 5, n5: 10, h5: 6, n10: 10, h10: 5, avg5: 0.6, excess: -0.4, state: '已结算' }
];

const SUG_KIND = { hard: '规则类', profile: '偏好类', prompt: '提示词', soft: '软性' };
const SUG_STATE = {
  pending: { label: '待你审核', tone: 'todo' },
  approved: { label: '已生效', tone: 'done' },
  adopted: { label: '已采纳生效', tone: 'done' },
  rejected: { label: '已驳回', tone: 'off' },
  thinking: { label: '重思考中', tone: 'run' }
};
const SUG_AUDIT = {
  pass: { label: 'AI 通过', tone: 'done' },
  fail: { label: 'AI 未通过', tone: 'bad' },
  pending: { label: 'AI 待审', tone: 'run' }
};

const SUG_ROWS = [
  {
    id: 3024, kind: 'hard', agent: 'RiskAgent', title: '追高拦截容忍度 3% → 5%',
    reason: '近 20 次拦截里 6 次拦错，被拦标的后 5 日平均 +4.8%，全部在容忍度 3%–5% 区间内。',
    before: '现价高于建仓参考价 3% 即拦截', after: '高于 5% 才拦截，3%–5% 改为减半仓试建仓',
    impact: 'high', audit: 'pass',
    auditReason: '样本 20 笔、跨 4 个板块，方向与既有风控目标不冲突；影响面是可量化阈值，不是行为约束，判定通过。',
    auditMode: 'ai', status: 'pending', ruleId: 'RC-1031', rvId: 1043,
    evidence: { count: 6, reviews: [1043, 1037], batches: ['2026-11-12', '2026-11-10'] },
    writesTo: '生效规则表 RC-1031（rule_change 留痕，二次确认后生效）',
    effectiveWhen: '规则审计二次确认通过后的下一个交易日开始',
    traces: [
      { time: '2026-11-16 15:40', title: 'AI 辩证审核通过', body: '反方观点：放宽后会放大追高亏损。结论：用减半仓试建仓对冲，风险敞口不增加。', tone: 'ok' },
      { time: '2026-11-16 15:22', title: 'ReviewAgent 提出建议', body: '来源：天孚通信影子复盘 + 京东方A 复盘，共 2 笔拦截争议。', tone: 'info' }
    ]
  },
  {
    id: 3023, kind: 'prompt', agent: 'ScoreAgent', title: '板块退潮时给「政策利好」加分打折',
    reason: '3 笔亏损都是政策利好拉高评分、但板块资金已流出。',
    before: '政策利好固定 +8 分', after: '板块 3 日主力净流出时，政策利好加分乘以 0.5',
    impact: 'low', audit: 'pending', auditReason: '', auditMode: 'ai', status: 'pending',
    ruleId: null, rvId: 1042,
    evidence: { count: 3, reviews: [1042, 1033], batches: ['2026-11-12', '2026-11-10'] },
    writesTo: 'ScoreAgent 提示词模板（不改评分因子结构）',
    effectiveWhen: '你确认生效后立即生效',
    traces: [{ time: '2026-11-16 15:10', title: 'ReviewAgent 提出建议', body: '来源：隆基绿能、紫光国微复盘。等待 AI 辩证审核。', tone: 'info' }]
  },
  {
    id: 3022, kind: 'profile', agent: 'PreferenceAgent', title: '单笔最大可接受亏损 1.5% → 1.0%',
    reason: '两次触发 1.5% 亏损都在情绪化补仓之后，你的实际承受力更接近 1%。',
    before: '单笔最大亏损 1.5%（账户总值）', after: '单笔最大亏损 1.0%，超出直接禁止加仓',
    impact: 'low', audit: 'pass',
    auditReason: '属于个人偏好收紧，不改变系统逻辑；历史 30 笔里有 4 笔会被提前砍掉，其中 3 笔后来确实继续跌。',
    auditMode: 'ai', status: 'pending', ruleId: null, rvId: 1031,
    evidence: { count: 4, reviews: [1031], batches: ['2026-11-10'] },
    writesTo: '偏好档案（只影响给你的建议口径）',
    effectiveWhen: '你确认生效后立即生效',
    traces: [{ time: '2026-11-13 16:05', title: 'AI 辩证审核通过', body: '反方：更严的止损会增加被震荡洗出的次数。结论：代价可接受。', tone: 'ok' }]
  },
  {
    id: 3020, kind: 'soft', agent: 'HoldAgent', title: '浮盈超过 6% 后不再加仓',
    reason: '4 笔加仓发生在浮盈 6% 之后，其中 3 笔把盈利加成了亏损。',
    before: '加仓只看剩余仓位额度', after: '浮盈 > 6% 时加仓需你手动确认',
    impact: 'high', audit: 'fail',
    auditReason: '样本只有 4 笔，其中 3 笔还是同一板块的同一段行情，不足以当成规律；现在生效等于用 4 个样本限制你的主要盈利来源。',
    auditMode: 'ai', status: 'pending', ruleId: null, rvId: 1041,
    evidence: { count: 4, reviews: [1041], batches: ['2026-11-11'] },
    writesTo: '持仓 Agent 行为约束（会影响加仓建议）',
    effectiveWhen: '强制采纳需写理由，留痕后可回滚',
    traces: [
      { time: '2026-11-12 09:20', title: 'AI 辩证审核未通过', body: '理由：样本不足且同板块重复计数，建议攒到 10 笔以上再提。', tone: 'err' },
      { time: '2026-11-11 16:30', title: 'ReviewAgent 提出建议', body: '来源：航发动力复盘。', tone: 'info' }
    ]
  },
  {
    id: 3018, kind: 'hard', agent: 'TradeAgent', title: '持仓 ≤ 3 日的超短建仓需二次确认',
    reason: '超短档 6 笔只有 1 笔赚钱，累计 -14.6%，是唯一稳定亏钱的档位。',
    before: '超短建仓与正常建仓同一流程', after: '预计持仓 ≤ 3 日时，弹窗二次确认并写明理由',
    impact: 'high', audit: 'pass',
    auditReason: '亏损集中在同一档、可复核；不禁止只做确认，属于轻约束。',
    auditMode: 'ai', status: 'adopted', ruleId: 'RC-1052', rvId: null,
    evidence: { count: 6, reviews: [1032, 1033], batches: ['2026-11-10'] },
    writesTo: '生效规则表 RC-1052',
    effectiveWhen: '已于 2026-11-12 生效',
    traces: [
      { time: '2026-11-12 10:02', title: '你二次确认生效', body: '写入 rule_change，规则 RC-1052 生效。', tone: 'ok' },
      { time: '2026-11-11 17:10', title: 'AI 辩证审核通过', body: '反方：会拖慢超短反应速度。结论：超短本来就是亏损来源，慢一点可接受。', tone: 'info' }
    ]
  },
  {
    id: 3015, kind: 'hard', agent: 'RiskAgent', title: '连亏 3 笔后当日停止新建仓',
    reason: '连亏后第二天继续开仓，胜率从 58% 掉到 21%。',
    before: '每日建仓只受额度限制', after: '连续 3 笔亏损后，当日不再产生新建仓方案',
    impact: 'high', audit: 'fail',
    auditReason: '样本 2 次，且两次都在大盘急跌周里，无法区分是你的状态问题还是行情问题。',
    auditMode: 'ai', status: 'rejected', rejectReason: '混淆了行情和人的状态，先把大盘因素剔除后再提。', ruleId: null, rvId: null,
    evidence: { count: 2, reviews: [1037], batches: ['2026-11-10'] },
    writesTo: '—', effectiveWhen: '—',
    traces: [
      { time: '2026-11-11 11:20', title: '你驳回', body: '理由：混淆了行情和人的状态，先把大盘因素剔除后再提。', tone: 'warn' },
      { time: '2026-11-10 16:40', title: 'AI 辩证审核未通过', body: '理由：样本 2 次，均在系统性下跌周。', tone: 'err' }
    ]
  }
];

const FC_ROWS = [
  { id: 'FC-08', name: '板块 3 日主力净流入占比', src: '复盘归纳', from: [1042, 1033], samples: 42, win: 0.57, ic: 0.041, verify: 'insufficient', verdict: '方向对，但和板块热度高度重复，需要先去掉共线性', status: 'candidate' },
  { id: 'FC-11', name: '放量突破后 2 日缩量回踩幅度', src: '复盘归纳', from: [1041], samples: 18, win: 0.61, ic: 0.052, verify: 'pass', verdict: '在长持档有效，短线档几乎没用', status: 'testing' },
  { id: 'FC-14', name: '被拦截后 5 日补涨天数', src: '人工提出', from: [1043], samples: 6, win: 0.83, ic: null, verify: 'insufficient', verdict: '样本太少，专门用来验证追高拦截该不该放宽', status: 'candidate' },
  { id: 'FC-16', name: '消息面利空 1 小时内的承接量', src: 'AI 挖掘', from: [1037], samples: 9, win: 0.33, ic: -0.018, verify: 'fail', verdict: '验证下来是反的：承接量大的第二天反而更容易跌', status: 'rejected' },
  { id: 'FC-19', name: '北向资金连续净买入天数', src: '人工提出', from: [], samples: 55, win: 0.49, ic: 0.006, verify: 'fail', verdict: '接近随机，不建议再花时间', status: 'archived' }
];

function rvMoney(n) {
  if (n == null) return '<span class="dim">—</span>';
  const abs = Math.abs(Math.round(n)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return '<span class="mono ' + (n >= 0 ? 'wo-up' : 'wo-down') + '">' + (n > 0 ? '+' : n < 0 ? '-' : '') + abs + '</span>';
}
function rvPct(v, suffix) {
  if (v == null) return '<span class="dim">—</span>';
  return '<span class="mono ' + (v >= 0 ? 'wo-up' : 'wo-down') + '">' + (v > 0 ? '+' : '') + v.toFixed(1) + (suffix || '%') + '</span>';
}
function rvRate(hit, n, max) {
  if (!n) return '<span class="dim">未到期</span>';
  const r = hit / n;
  return '<span class="' + (r >= 0.5 ? 'ok-t' : 'bad-t') + '">' + Math.round(r * 100) + '%</span> <span class="dim mono">' + hit + '/' + n + '</span>';
}
function rvBoardBar() {
  return '<div class="rv-boards"><div class="cp-chips">' + RV_BOARDS.map((b) =>
    '<button class="cp-chip ' + (state.rvBoard === b[0] ? 'active' : '') + '" data-action="rv-board" data-b="' + b[0] + '">' + b[1] + '</button>').join('') + '</div>' +
    '<span class="hint">' + esc(RV_BOARD_NOTE[state.rvBoard] || '') + '</span></div>';
}

/* ----- 看板：组合复盘 ----- */
function rvBoardAttr() {
  const r = PORT_RANGE;
  const maxC = Math.max.apply(null, PORT_HOLD.map((h) => Math.abs(h.contrib)));
  const stats = [
    { label: r.label + '累计盈亏', value: (r.cumPct >= 0 ? '+' : '') + r.cumPct.toFixed(1) + '%', sub: r.trades + ' 笔真实成交，影子复盘不计入', tone: r.cumPct >= 0 ? 'up' : 'down' },
    { label: '当日组合盈亏', value: (r.todayPct >= 0 ? '+' : '') + r.todayPct.toFixed(2) + '%', sub: rvMoneyInt(r.todayAmount), tone: r.todayPct >= 0 ? 'up' : 'down' },
    { label: '浮盈亏 / 当前市值', value: '+' + (r.unrealized / 10000).toFixed(2) + ' 万', sub: '市值 ' + (r.value / 10000).toFixed(1) + ' 万 · 成本 ' + (r.cost / 10000).toFixed(1) + ' 万', tone: 'up' },
    { label: '最大回撤', value: r.maxDD.pct.toFixed(1) + '%', sub: r.maxDD.from + ' → ' + r.maxDD.to, tone: 'down' }
  ];
  const daily = PORT_DAILY.map((d) => {
    const w = Math.min(100, Math.abs(d.pct) / 2.4 * 100);
    return '<tr><td class="mono">' + esc(d.date) + '</td>' +
      '<td>' + rvPct(d.pct) + '</td>' +
      '<td><span class="pd-bar"><i class="' + (d.pct >= 0 ? 'pos' : 'neg') + '" style="width:' + w.toFixed(0) + '%"></i></span></td>' +
      '<td class="mono">' + rvMoney(d.amount) + '</td>' +
      '<td class="dim">' + esc(d.note) + '</td></tr>';
  }).join('');
  const hold = PORT_HOLD.map((h) => {
    const w = Math.abs(h.contrib) / maxC * 100;
    return '<tr><td><span class="cp-name">' + esc(h.name) + ' <span class="mono dim">' + h.code + '</span></span></td>' +
      '<td class="mono">' + h.weight + '%</td>' +
      '<td>' + rvPct(h.pnlPct) + '</td>' +
      '<td><span class="pd-bar"><i class="' + (h.contrib >= 0 ? 'pos' : 'neg') + '" style="width:' + w.toFixed(0) + '%"></i></span> <span class="mono ' + (h.contrib >= 0 ? 'wo-up' : 'wo-down') + '">' + (h.contrib > 0 ? '+' : '') + h.contrib.toFixed(1) + 'pp</span></td>' +
      '<td>' + (h.exec === '未按计划' ? tag(h.exec, 'red') : h.exec === '提前止盈' ? tag(h.exec, 'gold') : tag(h.exec, 'green')) + '</td>' +
      '<td class="dim">' + esc(h.advice) + (h.rvId ? ' <button class="btn link xs" data-nav="#/reviews?id=' + h.rvId + '">复盘 ' + icon('arrow', 'sm') + '</button>' : '') + '</td></tr>';
  }).join('');
  const cycle = PORT_CYCLE.map((c) => {
    return '<tr><td>' + esc(c.label) + '</td>' +
      '<td class="mono">' + c.trades + '</td>' +
      '<td><span class="' + (c.win >= 0.5 ? 'ok-t' : 'bad-t') + '">' + Math.round(c.win * 100) + '%</span></td>' +
      '<td>' + rvPct(c.avg) + '</td>' +
      '<td>' + rvPct(c.cum) + '</td>' +
      '<td class="dim">' + esc(c.verdict) +
        (c.sugId ? ' <button class="btn link xs" data-nav="#/reviews?board=sug&sgs=' + c.sugId + '">看对应建议 ' + icon('arrow', 'sm') + '</button>' : '') + '</td></tr>';
  }).join('');
  return '<div class="metric-strip q4" style="margin-bottom:14px">' + stats.map((s) =>
    '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div><div class="metric-value ' + (s.tone || '') + '">' + esc(s.value) + '</div><div class="metric-sub">' + s.sub + '</div></div>').join('') + '</div>' +
    '<div class="card" style="margin-bottom:14px"><div class="card-title"><h3>当前持仓贡献明细</h3>' +
      '<span class="hint">贡献 = 这只票为区间累计盈亏贡献了多少个百分点</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>标的</th><th>仓位</th><th>浮动盈亏</th><th>贡献</th><th>执行</th><th>现在该做什么</th></tr></thead><tbody>' + hold + '</tbody></table></div></div>' +
    '<div class="grid-2">' +
      '<div class="card"><div class="card-title"><h3>每日盈亏（最近 7 个交易日）</h3></div>' +
        '<div class="table-wrap"><table><thead><tr><th>日期</th><th>盈亏</th><th></th><th>金额</th><th>发生了什么</th></tr></thead><tbody>' + daily + '</tbody></table></div></div>' +
      '<div class="card"><div class="card-title"><h3>按持仓周期分组</h3><span class="hint">顺序滚动口径，不是各档独立复利相加</span></div>' +
        '<div class="table-wrap"><table><thead><tr><th>周期</th><th>笔数</th><th>胜率</th><th>平均</th><th>累计</th><th>结论</th></tr></thead><tbody>' + cycle + '</tbody></table></div>' +
        '<div class="cap-note warn" style="margin-top:12px">' + icon('alert') + '<div><b>最亏的一天：</b>' + esc(r.worstDay.date) + ' ' + r.worstDay.pct.toFixed(1) + '% —— ' + esc(r.worstDay.why) + '<br>' +
          '<b>最赚的一天：</b>' + esc(r.bestDay.date) + ' +' + r.bestDay.pct.toFixed(1) + '% —— ' + esc(r.bestDay.why) + '</div></div></div>' +
    '</div>' +
    '<div class="cap-note" style="margin-top:14px">' + icon('info') + '<div>正式版这里还有两张图：组合盈亏曲线（近 30 日）和各持仓贡献瀑布，直接复用现有 ECharts 组件即可；原型先用表格给结论，因为你要的是「谁在拖后腿」，不是曲线本身。人工卖出后当天自动补一份复盘，不需要你手点。</div></div>';
}
function rvMoneyInt(n) { return '<span>' + (n >= 0 ? '+' : '-') + Math.abs(n).toLocaleString('en-US') + ' 元</span>'; }

/* ----- 看板：选股效果验证 ----- */
function trackSplit(item) {
  const seed = Number(String(item.code).slice(-3)) || 7;
  const t3 = Math.round(item.pnl * (0.3 + (seed % 9) / 22) * 10) / 10;
  const t10 = Math.round(item.pnl * (1.05 + (seed % 6) / 12) * 10) / 10;
  return { t3: t3, t5: item.pnl, t10: t10 };
}

function rvBoardTrack() {
  const totPicked = TRACK_ROWS.reduce((a, r) => a + r.picked, 0);
  const n5 = TRACK_ROWS.reduce((a, r) => a + r.n5, 0);
  const h5 = TRACK_ROWS.reduce((a, r) => a + r.h5, 0);
  const n10 = TRACK_ROWS.reduce((a, r) => a + r.n10, 0);
  const h10 = TRACK_ROWS.reduce((a, r) => a + r.h10, 0);
  const avgEx = TRACK_ROWS.filter((r) => r.excess != null).reduce((a, r) => a + r.excess, 0) / TRACK_ROWS.filter((r) => r.excess != null).length;
  const stats = [
    { label: '近 30 日选中', value: totPicked, sub: '7 个批次，含未建仓候选' },
    { label: 'T+5 胜率', value: Math.round(h5 / n5 * 100) + '%', sub: h5 + '/' + n5 + ' 笔，到期才计分母', tone: h5 / n5 >= 0.5 ? 'up' : 'down' },
    { label: 'T+10 胜率', value: (n10 ? Math.round(h10 / n10 * 100) + '%' : '—'), sub: n10 ? h10 + '/' + n10 + ' 笔' : '首批还没到 T+10', tone: 'info' },
    { label: '平均超额收益', value: (avgEx >= 0 ? '+' : '') + avgEx.toFixed(1) + '%', sub: '对比同期沪深300', tone: avgEx >= 0 ? 'up' : 'down' }
  ];
  const rows = TRACK_ROWS.map((r) => {
    const act = r.state === '已结算' ? 'off' : r.state === '未到期' ? 'run' : 'todo';
    return '<tr class="clickable' + (state.rvTrackDate === r.date ? ' row-sel' : '') + '" role="button" tabindex="0" data-action="rv-track-date" data-date="' + r.date + '">' +
      '<td class="mono">' + esc(r.date) + '</td>' +
      '<td class="mono">' + r.picked + '</td><td class="mono">' + r.buyable + '</td><td class="mono">' + r.opened + '</td>' +
      '<td>' + rvRate(r.h3, r.n3) + '</td><td>' + rvRate(r.h5, r.n5) + '</td><td>' + rvRate(r.h10, r.n10) + '</td>' +
      '<td>' + rvPct(r.avg5) + '</td>' +
      '<td class="num"><span class="state ' + act + '">' + esc(r.state) + '</span></td></tr>';
  }).join('');
  const items = batchItems(state.rvTrackDate);
  const tk = TRACK_ROWS.find((x) => x.date === state.rvTrackDate) || TRACK_ROWS[0];
  const detail = items.map((it) => {
    const p = trackSplit(it);
    return '<tr><td><span class="cp-name">' + esc(it.name) + ' <span class="mono dim">' + it.code + '</span></span></td>' +
      '<td>' + tag(it.label, it.label === '可建仓' ? 'green' : it.label === '建议关注' ? 'blue' : 'mute') + '</td>' +
      '<td class="mono">' + it.score + '</td>' +
      '<td>' + (it.took === '已建仓' ? tag('已建仓', 'outline') : '<span class="dim">未建仓</span>') + '</td>' +
      '<td>' + (tk.n3 ? rvPct(p.t3) : '<span class="dim">未到期</span>') + '</td>' +
      '<td>' + (tk.n5 ? rvPct(p.t5) : '<span class="dim">未到期</span>') + '</td>' +
      '<td>' + (tk.n10 ? rvPct(p.t10) : '<span class="dim">未到期</span>') + '</td>' +
      '<td class="num">' + (it.reviewId ? '<button class="btn link xs" data-nav="#/reviews?id=' + it.reviewId + '">复盘 ' + icon('arrow', 'sm') + '</button>' : '<span class="dim">' + esc(it.verdict) + '</span>') + '</td></tr>';
  }).join('');
  return '<div class="metric-strip q4" style="margin-bottom:14px">' + stats.map((s) =>
    '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div><div class="metric-value ' + (s.tone || '') + '">' + esc(s.value) + '</div><div class="metric-sub">' + esc(s.sub) + '</div></div>').join('') + '</div>' +
    '<div class="card" style="margin-bottom:14px"><div class="card-title"><h3>按选中日验证</h3><span class="hint">点一行看那批票的 T+N 明细</span><button class="btn link sm" data-nav="#/candidates?date=' + state.rvTrackDate + '">回候选池这批 ' + icon('arrow', 'sm') + '</button></div>' +
      '<div class="table-wrap"><table><thead><tr><th>选中日</th><th>候选</th><th>可建仓</th><th>建仓</th><th>T+3</th><th>T+5</th><th>T+10</th><th>平均涨幅</th><th>状态</th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><div class="card-title"><h3>' + esc(state.rvTrackDate) + ' 这批逐只 T+N 表现</h3><span class="hint">选中日收盘为基准，后 N 个交易日收盘对比' + (CAND_BATCH_DETAIL[state.rvTrackDate] ? '' : ' · 这批明细是原型演示数据') + '</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>标的</th><th>标签</th><th>评分</th><th>是否建仓</th><th>后 3 日</th><th>后 5 日</th><th>后 10 日</th><th></th></tr></thead><tbody>' + detail + '</tbody></table></div></div>' +
    '<div class="cap-note" style="margin-top:14px">' + icon('info') + '<div><b>统计口径：</b>T+N 胜率 = 选中日后第 N 个交易日收盘价高于选中日收盘价的比例；还没到期的不计入分母，也不算错。' +
      '这里包含<b>没建仓</b>的候选，衡量的是 AI 选得准不准；组合复盘只算真实成交，衡量的是你实际赚亏。两个口径不一样很正常——比如追高拦住的票在这里涨得好，恰恰说明拦错了（对应建议会进闭环建议队列）。' +
      '<br>另有 142 条影子/未到期记录待补算，补算任务在任务中心排队，不影响已结算批次。' +
      '<button class="btn link xs" data-action="rv-track-tasks">看补算任务 ' + icon('arrow', 'sm') + '</button></div></div>';
}

/* ----- 看板：闭环建议 ----- */
function sugById(id) { return SUG_ROWS.find((s) => s.id === Number(id)) || null; }

function filteredSugs() {
  return SUG_ROWS.filter((s) => {
    if (state.sgsFilter === 'pending' && s.status !== 'pending') return false;
    if (state.sgsFilter === 'done' && s.status === 'pending') return false;
    if (state.sgsAuditFilter === 'fail' && s.audit !== 'fail') return false;
    if (state.sgsAuditFilter === 'pass' && s.audit !== 'pass') return false;
    return true;
  });
}

function sugRowHtml(s) {
  const active = state.sgsId === s.id;
  const kindCls = s.kind === 'hard' ? 'blue' : s.kind === 'profile' ? 'gold' : s.kind === 'prompt' ? 'outline' : 'mute';
  const todo = s.status === 'pending';
  const rejectOpen = state.sgsRejectIn === s.id;
  const confirmOpen = state.sgsQuickConfirm === s.id;
  let acts = '';
  if (todo && !rejectOpen) {
    if (s.audit === 'pass') acts = rqBtn('sgsq-adopt', 'sgs', s.id, '采纳', true) + rqBtn('sgsq-reject', 'sgs', s.id, '驳回');
    else if (s.audit === 'pending') acts = rqBtn('sgsq-audit', 'sgs', s.id, '先让 AI 审', true) + rqBtn('sgsq-reject', 'sgs', s.id, '驳回');
    else acts = rqBtn('sgsq-why', 'sgs', s.id, '为什么没过') + rqBtn('sgsq-reject', 'sgs', s.id, '驳回');
    acts = '<span class="rq-acts">' + acts + '</span>';
  }
  return '<div class="cp-row sgs-row' + (active ? ' active' : '') + '" role="button" tabindex="0" data-action="sgs-select" data-sgs="' + s.id + '">' +
    '<div class="cp-row-top"><span class="cp-name">' + esc(s.title) + '</span><span class="spacer"></span>' +
      (s.impact === 'high' ? tag('高影响', 'gold') : tag('低影响', 'mute')) + '</div>' +
    '<div class="cp-row-reason">' + esc(s.reason) + '</div>' +
    '<div class="cp-row-foot">' +
      '<span class="mono dim">#' + s.id + '</span>' + tag(SUG_KIND[s.kind], kindCls) +
      '<span class="state ' + SUG_AUDIT[s.audit].tone + '">' + SUG_AUDIT[s.audit].label + '</span>' +
      '<span class="spacer"></span><span class="state ' + SUG_STATE[s.status].tone + '">' + SUG_STATE[s.status].label + '</span>' + acts +
    '</div>' +
    (confirmOpen ? '<div class="rq-reject rq-confirm" data-action="sgsq-keep">' +
        '<div><b>' + (s.impact === 'high' ? '高影响改动' : '规则类改动') + '</b>：' + esc(s.writesTo) + '，生效后立刻约束 Agent 行为。</div>' +
        '<div class="rq-reject-acts">' +
          rqBtn('sgsq-adopt', 'sgs', s.id, '确认生效', true) +
          '<button class="btn xs" data-action="sgsq-confirm-cancel">取消</button>' +
          '<span class="hint">这一步是二次确认，正式系统会同时写一条 rule_change</span>' +
        '</div></div>' : '') +
    (rejectOpen ? rqRejectHtml('sgsq', 'sgs', s.id, '为什么不采纳？理由会写进留痕') : '') +
  '</div>';
}

function sugContentTab(s) {
  return '<div class="rv-cmp">' +
      '<div class="rv-cmp-col"><div class="cp-list-title">调整前</div><div class="rv-cmp-txt">' + esc(s.before) + '</div></div>' +
      '<div class="rv-cmp-col"><div class="cp-list-title">调整后</div><div class="rv-cmp-txt">' + esc(s.after) + '</div></div>' +
    '</div>' +
    '<dl class="kv" style="margin-top:14px">' +
      '<dt>为什么提</dt><dd>' + esc(s.reason) + '</dd>' +
      '<dt>写到哪里</dt><dd>' + esc(s.writesTo) + '</dd>' +
      '<dt>什么时候生效</dt><dd>' + esc(s.effectiveWhen) + '</dd>' +
      '<dt>影响面</dt><dd>' + (s.impact === 'high' ? tag('高影响', 'gold') + ' <span class="hint">会改变 Agent 的行为边界，生效前需要二次确认</span>' : tag('低影响', 'mute') + ' <span class="hint">只改阈值或建议口径</span>') + '</dd>' +
      (s.ruleId ? '<dt>对应规则</dt><dd><button class="btn link xs" data-nav="#/system/rules?bucket=all&id=' + s.ruleId + '">' + s.ruleId + ' ' + icon('arrow', 'sm') + '</button></dd>' : '') +
    '</dl>';
}

function sugEvidenceTab(s) {
  const rv = s.evidence.reviews.map((id) => {
    const r = reviewById(id);
    if (!r) return '';
    return '<div class="ex-ev-row"><span>' + esc(r.name) + ' <span class="mono dim">' + r.code + '</span></span>' +
      '<span class="mono dim">#' + r.id + ' · ' + esc(r.exit) + '</span>' + (r.pnl >= 0 ? tag('+' + r.pnl.toFixed(1) + '%', 'red') : tag(r.pnl.toFixed(1) + '%', 'green')) +
      '<span class="spacer"></span><button class="btn link xs" data-nav="#/reviews?id=' + r.id + '">打开复盘 ' + icon('arrow', 'sm') + '</button></div>';
  }).join('');
  return '<dl class="kv">' +
      '<dt>样本量</dt><dd>' + s.evidence.count + ' 笔 <span class="hint">建议能不能生效，主要看这个数字够不够</span></dd>' +
      '<dt>来源批次</dt><dd>' + s.evidence.batches.map((d) => '<button class="btn link xs" data-nav="#/candidates?date=' + d + '">' + d + ' ' + icon('arrow', 'sm') + '</button>').join(' ') + '</dd>' +
      '<dt>验证窗口</dt><dd>建仓后 5 个交易日，同期沪深300 已剔除' + '</dd>' +
    '</dl>' +
    '<div class="cp-list-title" style="margin-top:16px">支撑这条建议的复盘</div>' +
    '<div class="ex-ev">' + (rv || '<div class="ex-ev-row"><span class="dim">没有具体复盘支撑，这条是 Agent 自己推出来的</span></div>') + '</div>' +
    (s.evidence.count < 10 ? '<div class="cap-note warn" style="margin-top:12px">' + icon('alert') + '<div>样本 10 笔以下时，AI 一般会判「不足以推广」。这时驳回比强制采纳更省时间——让它攒样本再重出一版。</div></div>' : '');
}

function sugAuditTab(s) {
  const aud = SUG_AUDIT[s.audit];
  let out = '<dl class="kv">' +
    '<dt>AI 结论</dt><dd><span class="state ' + aud.tone + '">' + aud.label + '</span></dd>' +
    '<dt>审核方式</dt><dd>' + (s.auditMode === 'manual' ? tag('人工复审', 'gold') : tag('AI 辩证审核', 'outline')) + ' <span class="hint">AI 结论是建议不是闸门——它说没通过时你仍可强制采纳，但要写理由并留痕</span></dd>' +
    '<dt>理由</dt><dd>' + (s.auditReason ? esc(s.auditReason) : '<span class="dim">还没跑审核</span>') + '</dd>' +
    (s.conflictNote ? '<dt>强制采纳理由</dt><dd>' + esc(s.conflictNote) + ' ' + tag('已写入 conflict_note', 'gold') + '</dd>' : '') +
    (s.rejectReason ? '<dt>你的驳回理由</dt><dd>' + esc(s.rejectReason) + '</dd>' : '') +
  '</dl>';
  if (s.status === 'pending' && s.audit === 'fail') {
    if (state.sgsConfirm === 'force-' + s.id) {
      out += '<div class="inline-confirm danger"><div class="ic-title">AI 没通过，仍要强制采纳？</div>' +
        '<div class="ic-desc">理由会写进 conflict_note 永久留痕，出事时能查到是谁拍的板。生效后可以回滚。</div>' +
        '<textarea class="input" id="sgs-force-reason" rows="3" placeholder="例如：我认这个方向，样本后面我自己盯"></textarea>' +
        '<div class="ic-actions"><button class="btn sm" data-action="sgs-cancel">取消</button>' +
        '<button class="btn danger sm" data-action="sgs-force-ok" data-sgs="' + s.id + '">确认强制采纳</button></div></div>';
    } else {
      out += '<div class="rv-acts"><button class="btn danger sm" data-action="sgs-force" data-sgs="' + s.id + '">强制采纳（需理由）</button>' +
        '<button class="btn sm" data-action="sgs-reraise" data-sgs="' + s.id + '">让 AI 重出一版</button>' +
        '<span class="hint">重出一版会带上 AI 的反对理由，通常比强制采纳划算。</span></div>';
    }
  } else if (s.status === 'pending' && s.audit === 'pending') {
    out += '<div class="cap-note accent" style="margin-top:12px">' + icon('rotate', 'sm') + '<div>排队等 AI 辩证审核。' +
      '<button class="btn link xs" data-action="sgs-audit-now" data-sgs="' + s.id + '">现在就审 ' + icon('arrow', 'sm') + '</button></div></div>';
  } else if (s.status === 'pending') {
    out += '<div class="cap-note" style="margin-top:12px">' + icon('check') + '<div>审核通过。这一步只是把结论摊给你看，还没写进规则表——生效要你在下面点确认。</div></div>';
  } else if (s.status === 'rejected') {
    out += '<div class="cap-note" style="margin-top:12px">' + icon('x') + '<div>已驳回，不再重复推送。理由本身留在记录里，AI 下次出类似建议时会被这条约束。</div></div>';
  } else {
    out += '<div class="cap-note" style="margin-top:12px">' + icon('undo', 'sm') + '<div>已生效的建议可以回滚。回滚不会删除留痕，只把规则标成失效，依赖它的 Agent 会被提示依据已变化。' +
      '<button class="btn xs" data-action="sgs-rollback" data-sgs="' + s.id + '">回滚</button>' +
      '<span class="hint">真实系统里这个按钮还在开发中，目前是禁用态。</span></div></div>';
  }
  return out;
}

function sugTraceTab(s) {
  return '<div class="timeline">' + s.traces.map((t) =>
    '<div class="tl-item"><span class="tl-dot ' + (t.tone || 'info') + '"></span>' +
    '<div class="tl-head"><span class="tl-title">' + esc(t.title) + '</span><span class="tl-time">' + esc(t.time) + '</span></div>' +
    '<div class="tl-body">' + esc(t.body) + '</div></div>').join('') + '</div>';
}

function sugDetailHtml(s) {
  const tabs = [['content', '建议内容'], ['evidence', '依据与样本'], ['audit', 'AI 审核'], ['trace', '处理记录']];
  let confirmHtml = '';
  if (state.sgsConfirm === 'adopt-' + s.id) {
    confirmHtml = '<div class="inline-confirm"><div class="ic-title">' + (s.kind === 'hard' ? '规则类建议需二次确认，确认生效？' : '确认采纳这条建议？') + '</div>' +
      '<div class="ic-desc">' + (s.kind === 'hard'
        ? esc(s.writesTo) + '。生效之后它只约束 AI 给你的建议口径，不会直接下单；改错了可以回到这一页回滚。'
        : esc(s.writesTo) + '。只改变给你的建议和口径，不触发任何交易动作。') + '</div>' +
      '<div class="ic-actions"><button class="btn sm" data-action="sgs-cancel">取消</button>' +
      '<button class="btn primary sm" data-action="sgs-adopt-ok" data-sgs="' + s.id + '">确认生效</button></div></div>';
  } else if (state.sgsConfirm === 'reject-' + s.id) {
    confirmHtml = '<div class="inline-confirm danger"><div class="ic-title">驳回这条建议</div>' +
      '<div class="ic-desc">理由必填。写清楚为什么不行，AI 才不会换个说法再提一遍。</div>' +
      '<textarea class="input" id="sgs-reject-reason" rows="3" placeholder="例如：把行情因素算成了人的问题，先剔除大盘再提"></textarea>' +
      '<div class="ic-actions"><button class="btn sm" data-action="sgs-cancel">取消</button>' +
      '<button class="btn danger sm" data-action="sgs-reject-ok" data-sgs="' + s.id + '">提交驳回</button></div></div>';
  }
  const body = state.sgsTab === 'evidence' ? sugEvidenceTab(s)
    : state.sgsTab === 'audit' ? sugAuditTab(s)
    : state.sgsTab === 'trace' ? sugTraceTab(s) : sugContentTab(s);
  const kindCls = s.kind === 'hard' ? 'blue' : s.kind === 'profile' ? 'gold' : s.kind === 'prompt' ? 'outline' : 'mute';
  const acts = s.status !== 'pending' ? ''
    : s.audit === 'fail'
      ? '<button class="btn sm" data-action="sgs-tab-jump" data-sgs="' + s.id + '" data-tab="audit">看 AI 的反对意见</button>' +
        '<button class="btn sm" data-action="sgs-reject" data-sgs="' + s.id + '">驳回</button>'
      : s.audit === 'pending'
        ? '<button class="btn sm" data-action="sgs-audit-now" data-sgs="' + s.id + '">先让 AI 审</button>' +
          '<button class="btn sm" data-action="sgs-reject" data-sgs="' + s.id + '">驳回</button>'
        : '<button class="btn primary sm" data-action="sgs-adopt" data-sgs="' + s.id + '">采纳生效</button>' +
          '<button class="btn sm" data-action="sgs-reject" data-sgs="' + s.id + '">驳回</button>';
  return '<div class="card">' +
    '<div class="detail-head"><div style="min-width:0">' +
      '<div class="detail-title">' + esc(s.title) + ' ' + tag(SUG_KIND[s.kind], kindCls) + '</div>' +
      '<div class="detail-sub">建议 #' + s.id + ' · 提出方 ' + esc(s.agent) + ' · 影响 ' + (s.impact === 'high' ? '高' : '低') + ' · 样本 ' + s.evidence.count + ' 笔</div>' +
      '<div class="detail-tags">' + '<span class="state ' + SUG_AUDIT[s.audit].tone + '">' + SUG_AUDIT[s.audit].label + '</span> ' +
        '<span class="state ' + SUG_STATE[s.status].tone + '">' + SUG_STATE[s.status].label + '</span>' +
        (s.rvId ? ' <button class="btn link xs" data-nav="#/reviews?id=' + s.rvId + '">从这笔复盘来的 ' + icon('arrow', 'sm') + '</button>' : '') +
      '</div></div>' +
      '<div class="spacer"></div><div class="cp-acts">' + acts + '</div>' +
    '</div>' +
    '<div class="detail-tabs">' + tabs.map((t) =>
      '<button class="detail-tab ' + (state.sgsTab === t[0] ? 'active' : '') + '" data-action="sgs-tab" data-tab="' + t[0] + '">' + t[1] +
      (t[0] === 'audit' && s.audit === 'fail' ? ' ' + tag('未通过', 'red') : '') + '</button>').join('') + '</div>' +
    '<div class="cp-tab-body">' + confirmHtml + body + '</div>' +
  '</div>';
}

function rvBoardSug() {
  const list = filteredSugs();
  const sel = list.find((s) => s.id === state.sgsId) || list[0] || SUG_ROWS[0];
  state.sgsId = sel.id;
  const pend = SUG_ROWS.filter((s) => s.status === 'pending').length;
  const fail = SUG_ROWS.filter((s) => s.audit === 'fail' && s.status === 'pending').length;
  const hard = SUG_ROWS.filter((s) => s.kind === 'hard' && s.status === 'pending').length;
  const live = SUG_ROWS.filter((s) => s.status === 'adopted' || s.status === 'approved').length;
  const stats = [
    { label: '待你审核', value: pend, sub: 'AI 审过了才排到你面前', tone: pend ? 'warn' : '' },
    { label: 'AI 未通过', value: fail, sub: '驳回比强制采纳省事', tone: fail ? 'err' : '' },
    { label: '规则类待确认', value: hard, sub: '需二次确认', tone: hard ? 'warn' : '' },
    { label: '已生效', value: live, sub: '含偏好与提示词改动' }
  ];
  const f1 = [['', '全部'], ['pending', '待你审核'], ['done', '已处理']];
  const f2 = [['', 'AI 结论全部'], ['pass', 'AI 通过'], ['fail', 'AI 未通过']];
  return '<div class="cp-toolbar">' +
      '<button class="btn sm" data-action="sgs-audit-all">' + icon('rotate', 'sm') + '增量 AI 审核' + (pend ? '（' + pend + ' 条）' : '') + '</button>' +
      '<span class="hint">AI 结论只是建议不是闸门：它说没通过时你仍可强制采纳，但要写理由并留痕。</span></div>' +
    '<div class="metric-strip q4" style="margin-bottom:14px">' + stats.map((s) =>
      '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div><div class="metric-value ' + (s.tone || '') + '">' + esc(s.value) + '</div><div class="metric-sub">' + esc(s.sub) + '</div></div>').join('') + '</div>' +
    '<div class="cp-toolbar"><div class="cp-chips">' + f1.map((f) =>
      '<button class="cp-chip ' + (state.sgsFilter === f[0] ? 'active' : '') + '" data-action="sgs-filter" data-f="' + f[0] + '">' + f[1] + '</button>').join('') + '</div>' +
      '<div class="cp-chips">' + f2.map((f) =>
      '<button class="cp-chip ' + (state.sgsAuditFilter === f[0] ? 'active' : '') + '" data-action="sgs-audit-filter" data-f="' + f[0] + '">' + f[1] + '</button>').join('') + '</div>' +
      '<span class="hint">命中 ' + list.length + ' / ' + SUG_ROWS.length + '</span></div>' +
    '<div class="cp-layout">' +
      '<div class="card cp-list-card">' + rqBarHtml(SUG_ROWS.filter((s) => s.status === 'pending').length) + '<div class="cp-list" id="sgs-list">' + (list.length ? list.map(sugRowHtml).join('') : '<div class="wo-empty" style="padding:14px">这个筛选下没有建议。</div>') + '</div></div>' +
      '<div class="cp-detail" id="sgs-detail">' + sugDetailHtml(sel) + '</div>' +
    '</div>' +
    '<div class="cap-note" style="margin-top:14px">' + icon('info') + '<div>逐笔复盘里看到的是<b>这一笔产出的建议</b>；这里是<b>全量建议队列</b>，同一个 Agent 的多笔复盘会合并成一条，还会带上 AI 辩证审核的反对意见。建议不会自己变成规则：AI 通过 → 你确认 → 规则审计二次确认，三关都过才改行为。</div></div>';
}

/* ----- 看板：候选因子 ----- */
const FC_VERIFY = {
  pass: { label: '验证通过', tone: 'done' },
  fail: { label: '验证不通过', tone: 'bad' },
  insufficient: { label: '样本不足', tone: 'off' }
};
const FC_STATUS = {
  candidate: { label: '候选', tone: 'todo' },
  testing: { label: '回测中', tone: 'run' },
  rejected: { label: '已否掉', tone: 'off' },
  archived: { label: '已归档', tone: 'off' }
};

function rvBoardFactor() {
  const rows = FC_ROWS.map((f) => {
    const v = FC_VERIFY[f.verify];
    const st = FC_STATUS[f.status];
    return '<tr><td><span class="cp-name">' + esc(f.name) + '</span><div class="cp-row-reason">' + esc(f.verdict) + '</div></td>' +
      '<td>' + tag(f.src, f.src === '人工提出' ? 'outline' : 'mute') + '</td>' +
      '<td class="mono">' + f.samples + '</td>' +
      '<td>' + (f.win == null ? '<span class="dim">—</span>' : '<span class="' + (f.win >= 0.5 ? 'ok-t' : 'bad-t') + '">' + Math.round(f.win * 100) + '%</span>') + '</td>' +
      '<td class="mono">' + (f.ic == null ? '<span class="dim">—</span>' : (f.ic > 0 ? '+' : '') + f.ic.toFixed(3)) + '</td>' +
      '<td><span class="state ' + v.tone + '">' + v.label + '</span></td>' +
      '<td><span class="state ' + st.tone + '">' + st.label + '</span></td>' +
      '<td class="num"><button class="btn xs" data-action="fc-backtest" data-fc="' + f.id + '">送去回测</button>' +
        (f.verify === 'pass' ? '<button class="btn primary xs" data-action="fc-propose" data-fc="' + f.id + '">提为因子建议</button>' : '') +
        (f.from.length ? '<button class="btn link xs" data-nav="#/reviews?id=' + f.from[0] + '">来源复盘 ' + icon('arrow', 'sm') + '</button>' : '') +
      '</td></tr>';
  }).join('');
  const passed = FC_ROWS.filter((f) => f.verify === 'pass').length;
  const stats = [
    { label: '候选因子', value: FC_ROWS.length, sub: '来自复盘归纳与人工提出' },
    { label: '验证通过', value: passed, sub: '只有这些能提建议', tone: 'info' },
    { label: '样本不足', value: FC_ROWS.filter((f) => f.verify === 'insufficient').length, sub: '先攒样本，不做结论' },
    { label: '已否掉 / 归档', value: FC_ROWS.filter((f) => f.status === 'rejected' || f.status === 'archived').length, sub: '留痕，不再重复验证' }
  ];
  return '<div class="metric-strip q4" style="margin-bottom:14px">' + stats.map((s) =>
    '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div><div class="metric-value ' + (s.tone || '') + '">' + esc(s.value) + '</div><div class="metric-sub">' + esc(s.sub) + '</div></div>').join('') + '</div>' +
    '<div class="card"><div class="card-title"><h3>候选因子清单</h3><span class="hint">IC = 因子值与后 5 日收益的 Rank 相关，0.03 以上才值得一提</span><button class="btn link sm" data-nav="#/system/factors">去因子回测 ' + icon('arrow', 'sm') + '</button></div>' +
      '<div class="table-wrap"><table><thead><tr><th>因子 / 验证下来是什么样</th><th>来源</th><th>样本</th><th>命中率</th><th>IC</th><th>验证</th><th>状态</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="cap-note" style="margin-top:14px">' + icon('info') + '<div>这一页只做一件事：把「复盘里看出的规律」变成「能回测的东西」。<b>验证不通过的因子不会自动消失</b>——它留在这里并标成已否掉，是为了下次有人（包括 AI）再提同一个想法时，能查到已经试过、结论是反的。提为因子建议后进规则审计，和规则走同一套确认流程。</div></div>';
}

/* ---------- 经验沉淀 ---------- */
const EXP_STATUS = {
  pending_review: { label: '待你审核', tone: 'todo' },
  processing: { label: '识别中', tone: 'run' },
  pending: { label: '待识别', tone: 'off' },
  active: { label: '已生效', tone: 'done' },
  rejected: { label: '已驳回', tone: 'off' },
  expired: { label: '已过期', tone: 'off' },
  rolled_back: { label: '已回滚', tone: 'bad' }
};
const EXP_STAGE = { 选股: 'blue', 建仓: 'gold', 持仓: 'green' };
const EXP_TABS = [['review', '待你审核'], ['active', '已生效'], ['run', '识别中'], ['archived', '已归档']];

const EXPERIENCE_ROWS = [
  {
    id: 'EXP-0021', stage: '持仓', impact: 'high', status: 'pending_review',
    title: '板块一起跌的时候，个股支撑位靠不住',
    content: '所属板块指数当日跌幅超过 1.5% 时，别等个股自己那条止损线，把止损位整体上移到成本价 -2%，先出来再说。',
    when: '同一板块 3 只以上持仓同时走弱，或板块指数放量跌破 5 日均线。',
    never: '板块只是缩量调整、个股仍在买入区且有独立利好时，不适用，容易被洗出去。',
    confidence: 0.61, hits: 2, first: '2026-11-12', last: '2026-11-16', merges: 1,
    from: [1042, 1031], agents: ['持仓监控 Agent', '离场决策 Agent'], source: '交易复盘自动沉淀',
    logs: [{ time: '2026-11-16 16:20', who: 'AI 归纳', text: '从 2 笔同板块亏损里归纳出来，标为高影响。' }]
  },
  {
    id: 'EXP-0020', stage: '建仓', impact: 'normal', status: 'pending_review',
    title: '分批止盈之后要写清楚怎么接回来',
    content: '方案里只要写了分批止盈，就必须同时写回补价和回补条件；不写就当方案不完整，别只留一个卖出动作。',
    when: '压力位分批减仓、仓位低于计划上限时。',
    never: '清仓离场、或标的已从候选池移除的不适用。',
    confidence: 0.55, hits: 1, first: '2026-11-16', last: '2026-11-16', merges: 0,
    from: [1044], agents: ['建仓方案 Agent'], source: '复盘建议采纳',
    logs: [{ time: '2026-11-16 15:30', who: '你采纳建议', text: '复盘 #1044 的建议写入经验库。' }]
  },
  {
    id: 'EXP-0018', stage: '选股', impact: 'normal', status: 'processing',
    title: '首板高开与当天回落的关系，还在归纳',
    content: '',
    when: '', never: '',
    confidence: null, hits: 0, first: '2026-11-13', last: '2026-11-16', merges: 0,
    from: [1037], agents: [], source: '识别任务处理中',
    logs: [{ time: '2026-11-16 11:00', who: '沉淀任务', text: '已聚合 6 笔相关复盘，正在做同主题合并，出结论前不可被检索。' }]
  },
  {
    id: 'EXP-0016', stage: '选股', impact: 'normal', status: 'active',
    title: '放量突破 20 日均线后 3 日不回踩，可以给高分',
    content: '突破 MA20 后连续 3 个交易日不回踩的标的，评分档位上调一档；回踩破位的直接打回观察。',
    when: '突破当日量能高于 5 日均量 1.5 倍。',
    never: '大盘处于单边下杀段（指数 MA20 下方）时不加档。',
    confidence: 0.78, hits: 14, first: '2026-10-22', last: '2026-11-16', merges: 4,
    from: [1041, 1032], agents: ['候选挖掘 Agent', '评分 Agent'], source: '交易复盘自动沉淀',
    logs: [
      { time: '2026-11-06 09:12', who: '你审核通过', text: '与 EXP-0005 合并，保留本条表述。' },
      { time: '2026-11-06 09:12', who: '系统', text: '注入候选挖掘与评分 Agent，开始参与检索。' }
    ]
  },
  {
    id: 'EXP-0012', stage: '建仓', impact: 'normal', status: 'active',
    title: '产业数据上调的票，第二根放量阳线可以加仓',
    content: '交付、订单、价格这类产业数据上调的标的，出现第二根放量阳线时可以把仓位加到上限，前提是单股仓位上限规则允许。',
    when: '首根阳线放量、第二根量能不低于首根 80%，且板块同步走强。',
    never: '纯情绪题材、没有可验证产业数据的加仓不适用。',
    confidence: 0.72, hits: 6, first: '2026-11-03', last: '2026-11-16', merges: 2,
    from: [1041], agents: ['建仓方案 Agent', '持仓监控 Agent'], source: '复盘建议采纳',
    logs: [{ time: '2026-11-16 18:22', who: '你审核通过', text: '来源复盘 #1041，采纳后直接生效。' }]
  },
  {
    id: 'EXP-0009', stage: '持仓', impact: 'normal', status: 'active',
    title: '题材退潮第一天不隔夜',
    content: '板块出现长上影线加尾盘跳水，第二天大概率低开；退潮首日先把仓位降到底仓，不等个股止损位被触发。',
    when: '题材类、连板类标的，板块整体处于高位放量。',
    never: '有明确产业催化且板块量能没放大的，不算退潮信号。',
    confidence: 0.69, hits: 9, first: '2026-10-28', last: '2026-11-13', merges: 3,
    from: [1033], agents: ['持仓监控 Agent'], source: '交易复盘自动沉淀',
    logs: [{ time: '2026-11-16 09:35', who: '你审核通过', text: '生效并注入持仓监控。' }]
  },
  {
    id: 'EXP-0007', stage: '选股', impact: 'high', status: 'rolled_back',
    title: '缩量回踩均线即卖出',
    content: '回踩 5 日均线且量能萎缩时减仓一半。',
    when: '', never: '',
    confidence: 0.44, hits: 11, first: '2026-10-19', last: '2026-11-06', merges: 1,
    from: [1032], agents: [], source: '交易复盘自动沉淀',
    rollbackReason: '生效后 3 笔按它卖出的标的平均少赚 6.2%，与「第二根放量阳线可加仓」直接冲突。',
    logs: [{ time: '2026-11-06 10:40', who: '你回滚', text: '标记失效并从检索结果移除，冲突交由规则审计裁决。' }]
  },
  {
    id: 'EXP-0004', stage: '建仓', impact: 'normal', status: 'rejected',
    title: '低开 2% 以内可以直接补仓',
    content: '', when: '', never: '',
    confidence: 0.31, hits: 0, first: '2026-10-30', last: '2026-10-30', merges: 0,
    from: [1031], agents: [], source: '交易复盘自动沉淀',
    logs: [{ time: '2026-11-02 14:02', who: '你驳回', text: '理由：这是亏损之后的补仓冲动，没有任何样本支持，不要沉淀成规则感。' }]
  }
];

function expById(id) { return EXPERIENCE_ROWS.find((e) => e.id === id) || null; }
function expPill(status) { const m = EXP_STATUS[status] || EXP_STATUS.pending; return '<span class="state ' + m.tone + '">' + m.label + '</span>'; }
function expBucketOf(e) {
  if (e.status === 'pending_review') return 'review';
  if (e.status === 'active') return 'active';
  if (e.status === 'processing' || e.status === 'pending') return 'run';
  return 'archived';
}
function filteredExperiences() {
  return EXPERIENCE_ROWS.filter((e) => {
    if (expBucketOf(e) !== state.expTab) return false;
    if (state.expStage && e.stage !== state.expStage) return false;
    return true;
  });
}

function expRowHtml(e) {
  const active = state.expId === e.id;
  const todo = e.status === 'pending_review';
  const rejectOpen = state.expRejectIn === e.id;
  const confirmOpen = state.expQuickConfirm === e.id;
  const acts = todo && !rejectOpen && !confirmOpen
    ? '<span class="rq-acts">' + rqBtn('expq-approve', 'exp', e.id, e.impact === 'high' ? '通过并生效' : '通过', true) + rqBtn('expq-reject', 'exp', e.id, '驳回') + '</span>'
    : '';
  return '<div class="cp-row ex-row' + (active ? ' active' : '') + '" role="button" tabindex="0" data-action="exp-select" data-exp="' + e.id + '">' +
    '<div class="cp-row-top">' +
      '<span class="mono dim">' + e.id + '</span>' +
      tag(e.stage, EXP_STAGE[e.stage] || 'mute') +
      (e.impact === 'high' ? tag('高影响', 'gold') : '') +
      (e.merges ? tag('合并 ' + e.merges + ' 次', 'mute') : '') +
      '<span class="spacer"></span>' + expPill(e.status) + acts +
    '</div>' +
    '<div class="cp-row-reason" style="white-space:normal">' + esc(e.title) + '</div>' +
    '<div class="cp-row-foot">' +
      (e.confidence == null ? '<span class="dim">置信度未出</span>' : '<span class="dim">置信 ' + e.confidence.toFixed(2) + '</span>') +
      '<span class="dim">命中 ' + e.hits + '</span>' +
      '<span class="mono dim">' + esc(e.first) + ' → ' + esc(e.last) + '</span>' +
    '</div>' +
    (confirmOpen ? '<div class="rq-reject rq-confirm" data-action="expq-keep">' +
        '<div><b>高影响经验</b>：注入后会影响持仓与建仓判断，且会同步生成规则建议送 AI 审计。</div>' +
        '<div class="rq-reject-acts">' +
          rqBtn('expq-approve', 'exp', e.id, '确认通过', true) +
          '<button class="btn xs" data-action="expq-confirm-cancel">取消</button>' +
        '</div></div>' : '') +
    (rejectOpen ? rqRejectHtml('expq', 'exp', e.id, '为什么不采信这条经验？') : '') +
  '</div>';
}

function expContentTab(e) {
  if (!e.content) {
    return '<div class="cp-scene-empty">这条还在识别中，AI 还没给出可用表述。识别中不可被 Agent 检索，也不需要你审核——出结论时会挪到「待你审核」。</div>' +
      '<div class="cap-note accent" style="margin-top:12px">' + icon('rotate', 'sm') + '<div>处理中：已聚合 ' + e.from.length + ' 笔相关复盘，正在做同主题去重与合并。</div></div>';
  }
  return '<div class="ex-content">' + esc(e.title) + '</div>' +
    '<div class="ex-body">' + esc(e.content) + '</div>' +
    '<dl class="kv" style="margin-top:14px">' +
      '<dt>什么时候用</dt><dd>' + esc(e.when || '—') + '</dd>' +
      '<dt>什么时候别用</dt><dd>' + esc(e.never || '—') + '</dd>' +
      '<dt>来源</dt><dd>' + esc(e.source) + '</dd>' +
    '</dl>' +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>经验是「大白话判断」，不是代码规则。它注入到 Agent 的提示词里影响打分和取舍，高影响的还必须再走一次规则审计才允许改变交易行为。</div></div>';
}

function expEvidenceTab(e) {
  if (!e.from.length) return '<div class="wo-empty">还没有可回溯的复盘来源。</div>';
  return '<div class="cp-list-title">由这些复盘攒出来的</div>' +
    '<div class="ex-ev">' + e.from.map((id) => {
      const r = reviewById(id);
      if (!r) return '';
      return '<div class="ex-ev-row">' +
        '<div><b>' + esc(r.name) + '</b> <span class="mono dim">' + r.code + '</span>' +
          '<div class="dim">#' + r.id + ' · 离场 ' + esc(r.exit) + ' · ' + esc(r.verdict) + '</div></div>' +
        '<div class="spacer"></div>' +
        '<div>' + rvPnl(r.pnl) + '</div>' +
        '<button class="btn link xs" data-nav="#/reviews?id=' + r.id + '">打开复盘 ' + icon('arrow', 'sm') + '</button>' +
      '</div>';
    }).join('') + '</div>' +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>同一条经验出现次数越多（' + esc(e.first) + ' 起 ' + e.hits + ' 次），置信度越稳；只有一两笔的经验我们会先攒着，不急着让它影响下单。</div></div>';
}

function expUsageTab(e) {
  const injected = e.status === 'active';
  return '<dl class="kv">' +
    '<dt>在用 Agent</dt><dd>' + (e.agents.length ? e.agents.map((a) => tag(a, 'blue')).join(' ') : '<span class="dim">尚未注入任何 Agent</span>') + '</dd>' +
    '<dt>注入位置</dt><dd>' + (injected ? '相关 Agent 的系统提示词 + 检索命中' : '<span class="dim">未生效，不会被检索到</span>') + '</dd>' +
    '<dt>命中次数</dt><dd class="mono">' + e.hits + ' 次 <span class="hint">复盘后按实际结果回算</span></dd>' +
    '<dt>置信度</dt><dd>' + (e.confidence == null ? '<span class="dim">—</span>' : '<b class="mono">' + e.confidence.toFixed(2) + '</b>' + ' <span class="hint">' + (e.confidence >= 0.7 ? '样本足够稳' : '还在攒样本') + '</span>') + '</dd>' +
    '<dt>影响等级</dt><dd>' + (e.impact === 'high' ? tag('高影响', 'gold') + ' <span class="hint">改动必须走规则审计</span>' : tag('一般', 'mute')) + '</dd>' +
    '<dt>首次 / 最近</dt><dd class="mono dim">' + esc(e.first) + ' → ' + esc(e.last) + '</dd>' +
  '</dl>' +
  (e.rollbackReason ? '<div class="cbi-note bad" style="margin-top:12px">' + icon('alert') + '<div>' + esc(e.rollbackReason) + '</div></div>' : '') +
  '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>只有「已生效」的经验才会被 Agent 检索到。驳回、过期、回滚都会立刻从检索结果里移除，但留档可以查。</div></div>';
}

function expLogTab(e) {
  return '<div class="timeline">' + e.logs.map((l) =>
    '<div class="tl-item"><span class="tl-dot ok"></span>' +
    '<div class="tl-head"><span class="tl-title">' + esc(l.who) + '</span><span class="tl-time">' + esc(l.time) + '</span></div>' +
    '<div class="tl-body">' + esc(l.text) + '</div></div>').join('') + '</div>';
}

function expActions(e) {
  const busy = state.expConfirm;
  if (e.status === 'pending_review') {
    if (busy === 'approve-' + e.id) {
      return '<div class="inline-confirm"><div class="ic-title">通过并生效？</div>' +
        '<div class="ic-desc">' + (e.impact === 'high'
          ? '高影响经验：通过后不会直接改交易行为，会同时生成一条规则建议送审计，规则审计再确认一次才真正落到下单参数上。'
          : '通过后会注入到 ' + (e.agents.length ? e.agents.join('、') : '相关 Agent') + '，Agent 打分和取舍会立刻带上这条判断。') + '</div>' +
        '<div class="ic-actions"><button class="btn sm" data-action="exp-cancel">取消</button>' +
        '<button class="btn primary sm" data-action="exp-approve-ok" data-exp="' + e.id + '">确认通过</button></div></div>';
    }
    if (busy === 'reject-' + e.id) {
      return '<div class="inline-confirm danger"><div class="ic-title">驳回这条经验</div>' +
        '<div class="ic-desc">原因必填。驳回不会删掉来源复盘，只是不让这条判断进入 Agent；AI 之后不会重复推同一条。</div>' +
        '<textarea class="input" id="exp-reason" rows="3" placeholder="例如：只有一两笔样本，先攒着别让它影响下单"></textarea>' +
        '<div class="ic-actions"><button class="btn sm" data-action="exp-cancel">取消</button>' +
        '<button class="btn danger sm" data-action="exp-reject-ok" data-exp="' + e.id + '">提交驳回</button></div></div>';
    }
    return '<div class="rv-acts"><button class="btn primary sm" data-action="exp-approve" data-exp="' + e.id + '">通过并生效</button>' +
      '<button class="btn sm" data-action="exp-reject" data-exp="' + e.id + '">驳回</button>' +
      (e.impact === 'high' ? '<button class="btn sm" data-action="exp-to-rule" data-exp="' + e.id + '">' + icon('workflow', 'sm') + '转成规则建议</button>' : '') +
      '<span class="hint">驳回同样会留痕，是你否掉 AI 的证据。</span></div>';
  }
  if (e.status === 'active') {
    if (busy === 'expire-' + e.id) {
      return '<div class="inline-confirm"><div class="ic-title">设为过期？</div>' +
        '<div class="ic-desc">过期等于「这条暂时不作为依据」：从检索结果移除，但保留证据，后面样本回来了可以重新审核生效。</div>' +
        '<div class="ic-actions"><button class="btn sm" data-action="exp-cancel">取消</button>' +
        '<button class="btn sm" data-action="exp-expire-ok" data-exp="' + e.id + '">确认过期</button></div></div>';
    }
    if (busy === 'rollback-' + e.id) {
      return '<div class="inline-confirm danger"><div class="ic-title">回滚这条已生效经验</div>' +
        '<div class="ic-desc">回滚会立刻从所有 Agent 的检索里移除，并把依赖它的持仓/方案标记为「依据已失效」，需要人工处理。除非已经看到实际亏损，否则先用过期。</div>' +
        '<textarea class="input" id="exp-reason" rows="3" placeholder="回滚原因（必填）"></textarea>' +
        '<div class="ic-actions"><button class="btn sm" data-action="exp-cancel">取消</button>' +
        '<button class="btn danger sm" data-action="exp-rollback-ok" data-exp="' + e.id + '">确认回滚</button></div></div>';
    }
    return '<div class="rv-acts"><button class="btn sm" data-action="exp-expire" data-exp="' + e.id + '">设为过期</button>' +
      '<button class="btn sm danger" data-action="exp-rollback" data-exp="' + e.id + '">回滚</button>' +
      '<span class="hint">已生效的经验可以随时过期或回滚，两者都会留痕。</span></div>';
  }
  if (e.status === 'processing' || e.status === 'pending') {
    return '<div class="cap-note accent" style="margin-top:14px">' + icon('rotate', 'sm') + '<div>识别中，还不能审核。等 AI 给出可用表述并做完同主题合并，会自动进入「待你审核」。</div></div>';
  }
  return '<div class="cap-note" style="margin-top:14px">' + icon('info') + '<div>这条已经终结（' + esc((EXP_STATUS[e.status] || {}).label) + '），只能查看留痕。要让判断重新生效，得由新的复盘再攒一版。</div></div>';
}

function expDetailHtml(e) {
  const tabs = [['content', '经验内容'], ['evidence', '来源证据'], ['usage', '使用情况'], ['log', '审核记录']];
  const body = state.expTab2 === 'evidence' ? expEvidenceTab(e)
    : state.expTab2 === 'usage' ? expUsageTab(e)
    : state.expTab2 === 'log' ? expLogTab(e) : expContentTab(e);
  return '<div class="card">' +
    '<div class="detail-head">' +
      '<div style="min-width:0">' +
        '<div class="detail-title">' + esc(e.title) + '</div>' +
        '<div class="detail-sub mono dim">' + e.id + ' · ' + esc(e.source) + ' · ' + esc(e.first) + ' 起出现 ' + e.hits + ' 次</div>' +
        '<div class="detail-tags">' + tag(e.stage + '阶段', EXP_STAGE[e.stage] || 'mute') + ' ' +
          (e.impact === 'high' ? tag('高影响', 'gold') : tag('一般影响', 'mute')) + ' ' +
          (e.merges ? tag('同主题合并 ' + e.merges + ' 次', 'outline') : '') + ' ' + expPill(e.status) + '</div>' +
      '</div>' +
      '<div class="spacer"></div>' +
      '<div class="cp-ext">' + e.from.slice(0, 2).map((id) => { const r = reviewById(id); return r ? '<button class="btn link xs" data-nav="#/reviews?id=' + id + '">' + esc(r.name) + ' 的复盘 ' + icon('arrow', 'sm') + '</button>' : ''; }).join('') + '</div>' +
    '</div>' +
    '<div class="detail-tabs">' + tabs.map((t) =>
      '<button class="detail-tab ' + (state.expTab2 === t[0] ? 'active' : '') + '" data-action="exp-tab" data-tab="' + t[0] + '">' + t[1] + '</button>').join('') + '</div>' +
    '<div class="cp-tab-body">' + body + '</div>' +
    expActions(e) +
  '</div>';
}

function renderExperience() {
  const list = filteredExperiences();
  const sel = list.find((e) => e.id === state.expId) || list[0] || expById(state.expId) || EXPERIENCE_ROWS[0];
  state.expId = sel.id;
  const pend = EXPERIENCE_ROWS.filter((e) => e.status === 'pending_review').length;
  const act = EXPERIENCE_ROWS.filter((e) => e.status === 'active').length;
  const run = EXPERIENCE_ROWS.filter((e) => e.status === 'processing' || e.status === 'pending').length;
  const stats = [
    { label: '待你审核', value: pend, sub: '通过才注入 Agent', tone: pend ? 'warn' : '' },
    { label: '已生效', value: act, sub: '正在被 Agent 使用', tone: 'ok' },
    { label: '识别中', value: run, sub: '还不可用' },
    { label: '高影响', value: EXPERIENCE_ROWS.filter((e) => e.impact === 'high').length, sub: '改动必须走规则审计', tone: 'info' }
  ];
  const stages = [['', '全部阶段'], ['选股', '选股'], ['建仓', '建仓'], ['持仓', '持仓']];
  return '<div>' +
    '<div class="subhead">' +
      '<div><h2>经验沉淀</h2><p>复盘攒出来的判断，你审核后才会进入 Agent 的脑子里。不认可的写一句驳回，它不会再来烦你。</p></div>' +
      '<div class="spacer"></div>' +
      '<div class="cp-chips">' + stages.map((s) =>
        '<button class="cp-chip ' + (state.expStage === s[0] ? 'active' : '') + '" data-action="exp-stage" data-s="' + s[0] + '">' + s[1] + '</button>').join('') + '</div>' +
    '</div>' +
    '<div class="metric-strip" style="margin-bottom:14px">' + stats.map((s) =>
      '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div><div class="metric-value ' + (s.tone || '') + '">' + esc(s.value) + '</div><div class="metric-sub">' + esc(s.sub) + '</div></div>').join('') + '</div>' +
    '<div class="cp-chips mode" style="margin-bottom:12px">' + EXP_TABS.map((t) =>
      '<button class="cp-chip ' + (state.expTab === t[0] ? 'active' : '') + '" data-action="exp-tab-main" data-t="' + t[0] + '">' + t[1] + '</button>').join('') + '</div>' +
    '<div class="cp-layout">' +
      '<div class="card cp-list-card">' + rqBarHtml(EXPERIENCE_ROWS.filter((e) => e.status === 'pending_review').length) + '<div class="cp-list" id="exp-list">' + (list.length ? list.map(expRowHtml).join('') : '<div class="wo-empty" style="padding:14px">这个队列暂时是空的。</div>') + '</div></div>' +
      '<div class="cp-detail" id="exp-detail">' + expDetailHtml(sel) + '</div>' +
    '</div>' +
    '<div class="cap-note" style="margin-top:14px">' + icon('info') +
      '<div>同主题的多条经验会自动合并（本库共合并 ' + EXPERIENCE_ROWS.reduce((s, e) => s + (e.merges || 0), 0) + ' 次），合并不会改你的审核结论；想改这条怎么用，直接在详情里过期或回滚。</div></div>' +
  '</div>';
}

function selectExp(id) {
  const e = expById(id);
  if (!e) return;
  state.expId = e.id;
  state.expConfirm = null;
  $$('.ex-row').forEach((el) => el.classList.toggle('active', el.dataset.exp === e.id));
  const box = $('#exp-detail');
  if (box) { box.innerHTML = expDetailHtml(e); hydrateIcons(box); }
  syncExpHash();
}

function syncExpHash() {
  if (state.route !== '#/experience') return;
  const next = '#/experience?id=' + state.expId;
  if (location.hash !== next) history.replaceState(null, '', next);
}

function applyExpApprove(e) {
  e.status = 'active';
  if (!e.agents.length) e.agents = ['持仓监控 Agent'];
  e.logs.unshift({ time: '刚刚', who: '你审核通过', text: e.impact === 'high' ? '生效，并生成规则建议送 AI 审计（规则确认前不改变下单参数）。' : '生效并注入相关 Agent，开始参与检索。' });
}

function applyExpReject(e, reason) {
  e.status = 'rejected';
  e.agents = [];
  e.logs.unshift({ time: '刚刚', who: '你驳回', text: '理由：' + reason });
}

function approveExperience(id) {
  const e = expById(id);
  if (!e) return;
  applyExpApprove(e);
  state.expTab = expBucketOf(e);
  renderView();
  toast(e.impact === 'high' ? '已生效，同时送去规则审计' : '已生效', e.impact === 'high'
    ? '高影响经验不会直接改交易参数，规则审计确认后才落地'
    : '现在 Agent 检索得到这条判断了', 'ok', {
      label: e.impact === 'high' ? '去规则建议' : '留在经验库',
      fn: () => { if (e.impact === 'high') location.hash = '#/system/rules'; }
    });
}

function rejectExperience(id) {
  const e = expById(id);
  const el = $('#exp-reason');
  const reason = el ? (el.value || '').trim() : '';
  if (!e) return;
  if (!reason) { if (el) { el.focus(); toast('需要写原因', '驳回要告诉 AI 为什么，不然是给它留了个再来一次的口子。', 'warn'); } return; }
  applyExpReject(e, reason);
  state.expConfirm = null;
  state.expTab = expBucketOf(e);
  renderView();
  toast('已驳回', '这条经验不会进入 Agent，同主题不再重复推送。', 'info');
}

function expireExperience(id) {
  const e = expById(id);
  if (!e) return;
  e.status = 'expired';
  e.agents = [];
  e.logs.unshift({ time: '刚刚', who: '你设为过期', text: '从检索结果移除，证据保留，可重新审核生效。' });
  state.expTab = expBucketOf(e);
  renderView();
  toast('已设为过期', 'Agent 不再检索到这条，随时可以重新审核放回。', 'info');
}

function rollbackExperience(id) {
  const e = expById(id);
  const el = $('#exp-reason');
  const reason = el ? (el.value || '').trim() : '';
  if (!e) return;
  if (!reason) { if (el) { el.focus(); toast('需要写原因', '回滚要留原因，后面别人查这条时得知道为什么被撤。', 'warn'); } return; }
  e.status = 'rolled_back';
  e.agents = [];
  e.rollbackReason = reason;
  e.logs.unshift({ time: '刚刚', who: '你回滚', text: '原因：' + reason + '。依赖此经验的持仓与方案已标记「依据已失效」。' });
  state.expConfirm = null;
  state.expTab = expBucketOf(e);
  renderView();
  toast('已回滚', '已从所有 Agent 移除，受影响持仓需要在持仓页人工确认。', 'warn');
}

/* ---------- 渲染 ---------- */
function renderView() {
  const route = state.route;
  let html = '';
  if (route === '#/overview') html = renderWorkspaceOverview();
  else if (route === '#/candidates') html = renderCandidates();
  else if (route === '#/reviews') html = renderReviews();
  else if (route === '#/experience') html = renderExperience();
  else if (route.startsWith('#/system/')) {
    const key = govTabKey();
    if (key === 'overview') html = renderOverview();
    else if (key === 'rules') html = renderRules();
    else if (key === 'factors') html = renderFactors();
    else if (key === 'capability') html = renderCapability();
    else html = renderOverview();
  } else {
    const info = PLACEHOLDERS[route];
    html = info ? renderPlaceholder(info) : renderOverview();
  }
  $('#view').innerHTML = html;
  hydrateIcons($('#view'));
  bindPage();
}

function refreshAll() {
  renderSidebar();
  renderCrumb();
  renderView();
}

function bindPage() {
  const search = $('#rule-search');
  if (search) {
    search.addEventListener('input', (e) => {
      state.ruleQuery = e.target.value;
      refreshRuleList();
    });
  }
  const agent = $('#rule-agent');
  if (agent) agent.addEventListener('change', (e) => { state.ruleAgent = e.target.value; refreshRuleList(); });
  const type = $('#rule-type');
  if (type) type.addEventListener('change', (e) => { state.ruleType = e.target.value; refreshRuleList(); });

  const sort = $('#rule-sort');
  if (sort) sort.addEventListener('change', (e) => { state.ruleSort = e.target.value; refreshRuleList(); });

  const fSearch = $('#factor-search');
  if (fSearch) fSearch.addEventListener('input', (e) => { state.factorQuery = e.target.value; renderFactorsTableOnly(); });
  const fCat = $('#factor-category');
  if (fCat) fCat.addEventListener('change', (e) => { state.factorCategory = e.target.value; renderFactorsTableOnly(); });

  const cSearch = $('#cand-search');
  if (cSearch) cSearch.addEventListener('input', (e) => { state.candQuery = e.target.value; refreshCandList(); });
  const cTier = $('#cand-tier');
  if (cTier) cTier.addEventListener('change', (e) => { state.candTier = e.target.value; refreshCandList(); });
}

function renderFactorsTableOnly() {
  const rows = state.factorHistory
    .filter((r) => !state.factorCategory || r.category === state.factorCategory)
    .filter((r) => !state.factorQuery.trim() || (r.name + ' ' + r.fid + ' ' + r.period).toLowerCase().includes(state.factorQuery.trim().toLowerCase()));
  const tbody = $('.card .table-wrap table tbody');
  if (tbody) {
    tbody.innerHTML = rows.map((r) =>
      '<tr class="clickable" data-action="factor-detail" data-id="' + r.id + '">' +
        '<td>' + esc(r.name) + '</td><td class="mono">' + esc(r.fid) + '</td><td>' + esc(r.category) + '</td><td>' + esc(r.period) + '</td>' +
        '<td class="num">' + (r.ic == null ? '—' : r.ic.toFixed(4)) + '</td>' +
        '<td class="num">' + (r.ir == null ? '—' : r.ir.toFixed(4)) + '</td>' +
        '<td class="num">' + (r.hit * 100).toFixed(1) + '%</td>' +
        '<td class="num">' + r.sample + '</td>' +
        '<td class="num">' + r.rank + '</td>' +
        '<td>' + factorStatusLabel(r) + '</td>' +
      '</tr>'
    ).join('');
  }
  const count = $('.filter-bar .small.muted');
  if (count) count.textContent = '共 ' + rows.length + ' 条';
}

/* ---------- 抽屉 ---------- */
function openDrawer(kind, payload) {
  const root = $('#drawer-root');
  let title = '';
  let sub = '';
  let body = '';
  if (kind === 'notes') {
    title = '导航与交互设计说明';
    sub = '原型所依据的判断，供你验收时对照';
    body = '<ol class="note-list">' +
      '<li><b>按交易节奏分组：</b>今日 → 研究 → 计划 → 复盘 → 系统。左侧从 17 项压到 14 项，先解决「每天先看什么」。</li>' +
      '<li><b>工作台总览改行动卡：</b>九张数据卡平铺回答不了「现在该干嘛」。四张行动卡直接把待办条目摆出来（决策 / 可建仓 / 风控 / 复盘），卡内每条都能直达处理现场；市况与持仓压成摘要行，后台任务与留痕收进底部。</li>' +
      '<li><b>治理页收进一个工作区：</b>治理总览、规则审计、因子回测、能力地图合并为「系统与治理」下的四个 Tab，低频页面不再占满侧边栏。</li>' +
      '<li><b>规则审计从看板改为队列：</b>五列拖拽很难回答「我现在该处理什么」，还容易误操作。现在按状态分队列，右边就地决策。</li>' +
      '<li><b>回滚/驳回改为内联确认：</b>保留上下文，原因必填，影响说明就在操作旁边，不弹全局 Modal。</li>' +
      '<li><b>流程可深链：</b>总览待办、健康度表、规则来源、能力地图之间都能直接跳转，不再靠 toast 提示。</li>' +
      '</ol>';
  } else if (kind === 'agent') {
    const a = AGENTS.find((x) => x.id === payload);
    if (a) {
      title = a.name + ' · ' + a.id;
      sub = '只读 Agent 能力定义';
      body = '<dl class="kv">' +
        '<dt>职责</dt><dd>' + esc(a.responsibility) + '</dd>' +
        '<dt>Agent 类型</dt><dd>' + esc(a.type) + '</dd>' +
        '<dt>权限等级</dt><dd>' + esc(a.authority) + '</dd>' +
        '<dt>知识范围</dt><dd>' + esc(a.scope) + '</dd>' +
        '<dt>必填输入</dt><dd>' + a.inputs.map((x) => tag(x, 'outline')).join(' ') + '</dd>' +
        '<dt>可选输入</dt><dd>' + (a.optional.length ? a.optional.map((x) => tag(x, 'outline')).join(' ') : '—') + '</dd>' +
        '<dt>输出</dt><dd>' + a.outputs.map((x) => tag(x, 'blue')).join(' ') + '</dd>' +
        '<dt>可引用</dt><dd>' + (a.canRef.length ? a.canRef.map((x) => tag(agentLabel(x), 'outline')).join(' ') : '—') + '</dd>' +
        '<dt>可调用</dt><dd>' + (a.canCall.length ? a.canCall.map((x) => tag(agentLabel(x), 'green')).join(' ') : '—') + '</dd>' +
        '<dt>不可做</dt><dd>' + a.cannot.map((x) => tag(x, 'red')).join(' ') + '</dd>' +
        '<dt>人工门禁</dt><dd>' + (a.gate ? tag('需要人工确认', 'gold') : tag('不需要', 'green')) + '</dd>' +
      '</dl>';
    }
  } else if (kind === 'factor') {
    const row = state.factorHistory.find((r) => r.id === payload);
    if (row) {
      title = row.name + ' · ' + row.period;
      sub = row.fid + ' · IC 月度回测';
      body = factorDetailHtml(row);
    }
  } else if (kind === 'kline-rv') {
    const r = reviewById(payload);
    if (!r) return;
    const base = CANDIDATE_POOL.find((x) => x.stock_code === r.code);
    const c = base ? Object.assign({}, base, { trade_date: r.exit }) : { stock_code: r.code, stock_name: r.name, trade_date: r.exit, trend: [] };
    title = r.name + ' · 日K线';
    sub = r.kind === 'shadow' ? '影子复盘对照：看被拦住那天之后的走势' : '正式页面复用现有 KlineChart，锚点传建仓日/离场日';
    body = candKlineHtml(c, r.kind === 'shadow' ? '拦截日' : '离场日');
  } else if (kind === 'kline') {
    const c = CANDIDATE_POOL.find((x) => x.stock_code === payload);
    if (!c) return;
    title = c.stock_name + ' · 日K线';
    sub = '正式页面复用现有 KlineChart 组件，这里演示入口与版式';
    body = candKlineHtml(c);
  } else if (kind === 'tasks') {
    const running = state.rules.filter((r) => r.audit === 'auditing');
    title = '任务中心';
    sub = running.length ? running.length + ' 个后台任务进行中' : '暂时没有后台任务';
    body = (running.length ?
      '<div class="stack">' + running.map((r) =>
        '<div class="audit-card"><div class="row"><b>' + esc(r.name) + '</b><span class="spacer"></span><span class="state run">审核中</span></div>' +
          '<div class="progress"><div class="progress-bar"></div></div>' +
          '<div class="small muted">第 ' + (r.round || 1) + ' 轮 AI 审核 · 完成后自动进入「等你决定」，无需守着页面。</div></div>'
      ).join('') + '</div>' +
      '<div class="cap-note" style="margin-top:14px">' + icon('info') + '<div>接入后端后，这里会显示规则审核、因子回测、建仓方案生成等任务的真实进度与失败重试入口。</div></div>'
      :
      '<div class="empty-list"><strong>没有运行中的任务</strong>提交增量 AI 审核或重新审核后，任务进度会显示在这里。</div>' +
      '<div class="cap-note" style="margin-top:14px">' + icon('clock') + '<div>正式接入后，规则 AI 审核、因子回测、建仓方案生成等后台任务会在这里显示进度，并在完成时通知当前页面刷新。</div></div>');
  }
  root.innerHTML = '<div class="drawer-mask" data-drawer-mask><div class="drawer" role="dialog" aria-modal="true">' +
    '<div class="drawer-head"><div><div class="drawer-title">' + esc(title) + '</div><div class="drawer-sub">' + esc(sub) + '</div></div>' +
      '<button class="icon-btn" data-action="close-drawer" aria-label="关闭">' + icon('x') + '</button></div>' +
    '<div class="drawer-body">' + body + '</div>' +
  '</div></div>';
  hydrateIcons(root);
}

function closeDrawer() {
  $('#drawer-root').innerHTML = '';
}

/* ---------- 命令面板 ---------- */
function paletteItems() {
  const items = [];
  NAV.forEach((g) => g.items.forEach((it) => items.push({ label: g.group + ' / ' + it.label, path: it.path })));
  GOV_TABS.forEach((t) => items.push({ label: '系统与治理 / ' + t.label, path: t.path }));
  RV_BOARDS.forEach((b) => { if (b[0] !== 'list') items.push({ label: '复盘 / 交易复盘 · ' + b[1], path: '#/reviews?board=' + b[0] }); });
  return items.filter((it, idx, arr) => arr.findIndex((x) => x.path === it.path) === idx);
}

function renderPalette(query) {
  const q = String(query || '').trim().toLowerCase();
  const items = paletteItems().filter((it) => !q || it.label.toLowerCase().includes(q));
  state.paletteIndex = Math.min(state.paletteIndex, Math.max(items.length - 1, 0));
  $('#palette-list').innerHTML = items.map((it, i) =>
    '<button class="palette-item ' + (i === state.paletteIndex ? 'sel' : '') + '" data-nav="' + it.path + '">' +
      icon('arrow', 'sm') + '<span>' + esc(it.label) + '</span><span class="path">' + esc(it.path.replace('#/', '')) + '</span>' +
    '</button>'
  ).join('') || '<div class="empty-list">没有匹配的页面。</div>';
  return items;
}

function openPalette() {
  $('#palette').hidden = false;
  state.paletteIndex = 0;
  renderPalette('');
  const input = $('#palette-input');
  input.value = '';
  setTimeout(() => input.focus(), 0);
}

function closePalette() {
  $('#palette').hidden = true;
}

/* ---------- 动作 ---------- */
function selectRule(id) {
  if (!id) return;
  state.selectedRuleId = id;
  state.pendingAction = null;
  state.ruleDetailTab = 'suggestion';
  $$('.rule-row').forEach((el) => el.classList.toggle('active', el.dataset.id === id));
  refreshRuleDetail();
  syncRuleHash();
}

function startAction(kind, id) {
  state.pendingAction = { kind, id };
  state.ruleDetailTab = 'suggestion';
  refreshRuleDetail();
  setTimeout(() => {
    const el = $('#confirm-reason');
    if (el) el.focus();
  }, 0);
}

function confirmAction(kind, id) {
  const rule = state.rules.find((r) => r.id === id);
  if (!rule) return;
  const reasonEl = $('#confirm-reason');
  const reason = reasonEl ? reasonEl.value.trim() : '';
  if ((kind === 'reject' || kind === 'rollback') && !reason) {
    toast('原因必填', kind === 'rollback' ? '回滚原因需要写入审计记录。' : '驳回原因需要写入审计记录。', 'warn');
    if (reasonEl) reasonEl.focus();
    return;
  }
  const now = '2026-11-16 17:' + String(20 + Math.floor(Math.random() * 30)).padStart(2, '0');
  const before = clone(rule);
  const prevBucket = state.ruleBucket;
  const undo = (label) => ({
    label: '撤销',
    fn: () => {
      const idx = state.rules.findIndex((r) => r.id === id);
      if (idx < 0) return;
      state.rules[idx] = before;
      state.ruleBucket = prevBucket;
      state.selectedRuleId = id;
      state.ruleDetailTab = 'suggestion';
      refreshAll();
      syncRuleHash();
      toast('已撤销', label + '已回退到操作前的状态，未写入留痕。', 'info');
    }
  });
  if (kind === 'approve') {
    const valueEl = $('#confirm-value');
    const value = valueEl ? valueEl.value.trim() : rule.suggested;
    if (!value) { toast('生效值必填', '采纳前请确认规则生效值。', 'warn'); if (valueEl) valueEl.focus(); return; }
    rule.status = 'active';
    rule.current = value;
    rule.timeline.push({
      time: now, title: '人工采纳并生效', actor: 'human',
      body: '写入 rule_change，全部 Agent 下一次调用起携带。' +
        (value !== rule.suggested ? '生效值由 AI 建议 ' + rule.suggested + ' 调整为 ' + value + '。' : '') +
        (reason ? ' 备注：' + reason : ''),
      tone: 'ok'
    });
    toast('已采纳并生效', '规则 ' + rule.id + ' 已写入留痕，全部 Agent 已更新。', 'ok', undo('采纳'));
  } else if (kind === 'reject') {
    rule.status = 'rejected';
    rule.timeline.push({ time: now, title: '人工驳回', actor: 'human', body: '原因：' + reason, tone: 'err' });
    toast('已驳回', '原因已写入留痕。该建议不会生效。', 'ok', undo('驳回'));
  } else if (kind === 'rollback') {
    rule.status = 'rolled_back';
    rule.timeline.push({ time: now, title: '人工回滚', actor: 'human', body: '原因：' + reason + '。全部 Agent 已停止携带该规则。', tone: 'warn' });
    toast('已回滚', '全部 Agent 已停止携带该规则，审计记录已写入。', 'warn', undo('回滚'));
  }
  state.pendingAction = null;
  state.ruleDetailTab = 'timeline';
  state.selectedRuleId = id;
  state.ruleBucket = kind === 'approve' ? 'active' : kind === 'reject' ? 'rejected' : 'rolled_back';
  refreshAll();
  syncRuleHash();
}

function reauditRule(id) {
  const rule = state.rules.find((r) => r.id === id);
  if (!rule) return;
  rule.audit = 'auditing';
  rule.round = (rule.round || 0) + 1;
  rule.timeline.push({ time: '2026-11-16 17:26', title: '重新触发 AI 审核', actor: 'human', body: '第 ' + rule.round + ' 轮审核已提交后台。', tone: 'info' });
  state.selectedRuleId = id;
  state.ruleBucket = 'auditing';
  syncRuleHash();
  toast('已提交审核', '规则 ' + rule.id + ' 第 ' + rule.round + ' 轮 AI 审核已提交，完成后自动刷新。', 'info');
  refreshAll();
  setTimeout(() => {
    const current = state.rules.find((r) => r.id === id);
    if (!current || current.audit !== 'auditing') return;
    current.audit = 'pass';
    current.confidence = 0.83;
    current.auditLog = {
      verdict: 'pass', round: current.round || 1, confidence: 0.83,
      support: '重新审核后样本与边界条件均已补齐。',
      dissent: '仍需关注小样本区间的波动。',
      boundary: '极端行情下建议人工复核。',
      evidenceRefs: ['最新复核样本'],
      model: 'audit-v2.3', at: '2026-11-16 17:28',
      reasoning: '{"verdict":"pass","confidence":0.83,"source":"reaudit"}'
    };
    current.timeline.push({ time: '2026-11-16 17:28', title: 'AI 审核通过', actor: 'ai', body: '置信度 0.83，等待人工审核。', tone: 'ok' });
    if (state.route === '#/system/rules' && state.ruleBucket === 'auditing') {
      state.ruleBucket = 'todo';
      state.selectedRuleId = id;
      syncRuleHash();
    }
    if (state.route === '#/system/rules' || state.route === '#/system/overview') refreshAll();
    toast('AI 审核完成', '规则 ' + id + ' 已通过，进入待处理队列。', 'ok');
  }, 2200);
}

function rereviewRule(id) {
  const rule = state.rules.find((r) => r.id === id);
  if (!rule) return;
  rule.status = 'pending';
  rule.timeline.push({ time: '2026-11-16 17:26', title: '重新进入人工审', body: '已驳回建议回到待审核状态。', tone: 'info' });
  state.selectedRuleId = id;
  state.ruleBucket = 'todo';
  toast('已回到待审核', '规则 ' + rule.id + ' 可重新采纳或驳回。', 'info');
  refreshAll();
}

function runIncrementalAudit() {
  const targets = state.rules.filter((r) => r.audit === 'pending' || r.audit === 'auditing');
  if (!targets.length) { toast('没有待审核项', '当前所有建议都已完成 AI 审核。', 'info'); return; }
  targets.forEach((r) => { r.audit = 'auditing'; });
  renderSidebar();
  if (state.route.startsWith('#/system/')) renderView();
  toast('已提交增量 AI 审核', '共 ' + targets.length + ' 条，完成后自动刷新。', 'info');
  setTimeout(() => {
    targets.forEach((t) => {
      const r = state.rules.find((x) => x.id === t.id);
      if (!r || r.audit !== 'auditing') return;
      r.audit = 'pass';
      r.confidence = 0.82;
      r.auditLog = {
        verdict: 'pass', round: (r.round || 1), confidence: 0.82,
        support: '增量审核样本与边界条件已补齐。',
        dissent: '仍需关注样本覆盖不足的区间。',
        boundary: '极端行情下建议人工复核。',
        evidenceRefs: ['增量审核样本'],
        model: 'audit-v2.3', at: '2026-11-16 17:29',
        reasoning: '{"verdict":"pass","confidence":0.82,"source":"incremental"}'
      };
      r.timeline.push({ time: '2026-11-16 17:29', title: 'AI 审核通过', actor: 'ai', body: '增量审核完成，置信度 0.82。', tone: 'ok' });
    });
    if (state.route === '#/system/rules' && state.ruleBucket === 'auditing') {
      state.ruleBucket = 'todo';
      if (targets[0]) state.selectedRuleId = targets[0].id;
      syncRuleHash();
    }
    if (state.route.startsWith('#/system/')) { renderSidebar(); renderView(); }
    toast('AI 审核完成', '增量审核已完成，结果已进入对应队列。', 'ok');
  }, 2400);
}

function offlineFactor(fid, reason) {
  const p = state.factors.find((x) => x.fid === fid);
  if (!p) return;
  state.factorConfirm = null;
  state.factors = state.factors.filter((x) => x.fid !== fid);
  state.factorHistory.unshift({
    id: 'IC-NEW-' + (2400 + Math.floor(Math.random() * 90)),
    fid: p.fid, name: p.name, category: p.category, period: '2026-11',
    ic: p.icHistory[p.icHistory.length - 1], ir: null, hit: 0.5,
    sample: 0, rank: 0, status: 'deprecated_candidate'
  });
  GOV_EVENTS.unshift({ time: '2026-11-16 17:26', title: '因子已下线：' + p.name, body: p.fid + ' 已退出每日打分。原因：' + reason, tone: 'warn' });
  toast('因子已下线', p.fid + ' 不再参与每日打分，决策已留痕。', 'warn');
  renderSidebar();
  renderView();
}

function keepFactor(fid) {
  const p = state.factors.find((x) => x.fid === fid);
  if (!p) return;
  state.factorConfirm = null;
  state.factors = state.factors.filter((x) => x.fid !== fid);
  GOV_EVENTS.unshift({ time: '2026-11-16 17:26', title: '因子保留：' + p.name, body: p.fid + ' 的下线建议被驳回，继续参与打分。', tone: 'info' });
  toast('已驳回下线建议', p.fid + ' 继续保留，决策已留痕。', 'info');
  renderSidebar();
  renderView();
}

function collabQuery() {
  const requester = $('#collab-requester').value;
  const target = $('#collab-target').value;
  const relation = $('#collab-relation').value;
  if (!requester || !target) { toast('请补全查询', '调用方和目标都需要选择。', 'warn'); return; }
  const rule = COLLAB_RULES.find((r) => r.requester === requester && r.target === target && r.relation === relation);
  state.collabResult = rule
    ? { requester, target, relation, allowed: rule.allowed, reason: rule.reason, audit: rule.audit }
    : { requester, target, relation, allowed: false, reason: '未声明', audit: false };
  const el = $('#collab-result');
  if (el) el.innerHTML = collabResultHtml();
}

/* ---------- 事件 ---------- */
document.addEventListener('click', (e) => {
  const chk = e.target.closest('input[data-check]');
  if (chk) { toggleRuleCheck(chk.dataset.check, chk.checked); return; }
  const navEl = e.target.closest('[data-nav]');
  if (navEl) {
    const bucket = navEl.dataset.bucket;
    if (bucket && (bucket === 'all' || bucket in bucketCounts())) {
      state.ruleBucket = bucket;
      state.pendingAction = null;
    }
    if (navEl.dataset.nav === '#/system/rules' && !bucket) state.ruleBucket = 'todo';
    location.hash = (bucket && navEl.dataset.nav === '#/system/rules')
      ? '#/system/rules?bucket=' + bucket
      : navEl.dataset.nav;
    closePalette();
    return;
  }

  const el = e.target.closest('[data-action]');
  if (!el) {
    if (e.target.matches('[data-drawer-mask]')) closeDrawer();
    return;
  }
  const action = el.dataset.action;
  const id = el.dataset.id;

  if (action === 'refresh') { toast('已刷新', '原型使用静态数据，正式接入后此处调用只读接口。', 'info'); return; }
  if (action === 'open-drawer') { openDrawer(el.dataset.drawer, id); return; }
  if (action === 'close-drawer') { closeDrawer(); return; }
  if (action === 'task-center') { openDrawer('tasks'); return; }
  if (action === 'open-palette') { openPalette(); return; }
  if (action === 'select-rule') { selectRule(id); return; }
  if (action === 'select-cand') { selectCand(el.dataset.cand); return; }
  if (action === 'cand-tab') { state.candTab = el.dataset.tab; const c = CANDIDATE_POOL.find((x) => x.stock_code === state.candId); const detail = $('#cand-detail'); if (detail && c) { detail.innerHTML = candDetailHtml(c); hydrateIcons(detail); } return; }
  if (action === 'cand-gen') {
    const c = CANDIDATE_POOL.find((x) => x.stock_code === el.dataset.cand);
    toast('已提交建仓方案生成', '「' + (c ? c.stock_name : '') + '」已进入生成队列，进度见任务中心', 'ok');
    return;
  }
  if (action === 'cand-kline') { openDrawer('kline', el.dataset.cand); return; }
  if (action === 'cand-mode') { state.candMode = el.dataset.mode; renderView(); syncCandHash(); return; }
  if (action === 'cand-batch') {
    state.candBatch = el.dataset.date;
    const d = document.querySelector('#cb-detail');
    if (d) { d.innerHTML = candBatchDetailHtml(state.candBatch); hydrateIcons(d); }
    $$('.cb-row').forEach((r) => r.classList.toggle('active', r.dataset.date === state.candBatch));
    syncCandHash();
    return;
  }
  if (action === 'cand-news-filter') { state.candNewsFilter = el.dataset.f; renderView(); return; }  if (action === 'cand-news-expand') { state.candNewsOpen = !state.candNewsOpen; renderView(); return; }
  if (action === 'cand-news-linked') { state.candNewsLinked = el.checked; renderView(); return; }
  if (action === 'cand-add-toggle') { state.candAddOpen = !state.candAddOpen; renderView(); if (state.candAddOpen) { const e = $('#add-code'); if (e) e.focus(); } return; }
  if (action === 'cand-add-cancel') { state.candAddOpen = false; renderView(); return; }
  if (action === 'cand-add-submit') { addManualCandidate(); return; }
  if (action === 'rv-select') { selectReview(el.dataset.rv); return; }
  if (action === 'rv-tab') { state.rvTab = el.dataset.tab; refreshRvDetail(); return; }
  if (action === 'rv-filter') { state.rvFilter = el.dataset.f; renderView(); syncRvHash(); return; }
  if (action === 'rv-clear-batch') { state.rvBatch = ''; renderView(); syncRvHash(); return; }
  if (action === 'rv-kline') { openDrawer('kline-rv', el.dataset.rv); return; }
  if (action === 'rv-adopt') { state.rvConfirm = 'adopt-' + el.dataset.rv; refreshRvDetail(); return; }
  if (action === 'rv-reject') { state.rvConfirm = 'reject-' + el.dataset.rv; refreshRvDetail(); const ta = $('#rv-reason'); if (ta) ta.focus(); return; }
  if (action === 'rv-cancel') { state.rvConfirm = null; refreshRvDetail(); return; }
  if (action === 'rv-adopt-ok') { adoptReview(el.dataset.rv); return; }
  if (action === 'rv-reject-ok') { rejectReview(el.dataset.rv); return; }
  if (action === 'rv-tab-jump') { state.rvTab = el.dataset.tab; refreshRvDetail(); return; }
  if (action === 'rv-board') { state.rvBoard = el.dataset.b; state.rvConfirm = null; state.sgsConfirm = null; renderView(); syncRvHash(); return; }
  if (action === 'rv-track-date') { state.rvTrackDate = el.dataset.date; renderView(); syncRvHash(); return; }
  if (action === 'rv-track-tasks') { openDrawer('tasks'); return; }
  if (action === 'sgs-select') { selectSug(el.dataset.sgs); return; }
  if (action === 'sgs-tab') { state.sgsTab = el.dataset.tab; refreshSugDetail(); return; }
  if (action === 'sgs-tab-jump') { state.sgsId = Number(el.dataset.sgs); state.sgsTab = el.dataset.tab; state.sgsConfirm = null; renderView(); syncRvHash(); return; }
  if (action === 'sgs-filter') { state.sgsFilter = el.dataset.f; renderView(); syncRvHash(); return; }
  if (action === 'sgs-audit-filter') { state.sgsAuditFilter = el.dataset.f; renderView(); syncRvHash(); return; }
  if (action === 'sgs-adopt') { state.sgsConfirm = 'adopt-' + el.dataset.sgs; refreshSugDetail(); return; }
  if (action === 'sgs-adopt-ok') { adoptSug(el.dataset.sgs); return; }
  if (action === 'sgs-reject') { state.sgsConfirm = 'reject-' + el.dataset.sgs; refreshSugDetail(); const rr = $('#sgs-reject-reason'); if (rr) rr.focus(); return; }
  if (action === 'sgs-reject-ok') { rejectSug(el.dataset.sgs); return; }
  if (action === 'sgs-force') { state.sgsConfirm = 'force-' + el.dataset.sgs; refreshSugDetail(); const fr = $('#sgs-force-reason'); if (fr) fr.focus(); return; }
  if (action === 'sgs-force-ok') { forceSug(el.dataset.sgs); return; }
  if (action === 'sgs-reraise') { reRaiseSug(el.dataset.sgs); return; }
  if (action === 'sgs-cancel') { state.sgsConfirm = null; refreshSugDetail(); return; }
  if (action === 'sgs-audit-now') { auditSugNow(el.dataset.sgs); return; }
  if (action === 'sgs-audit-all') { auditAllSugs(); return; }
  if (action === 'sgs-rollback') { rollbackSug(el.dataset.sgs); return; }
  /* 就地裁决：列表行上直接处理，处理完自动跳下一条 */
  if (action === 'rvq-adopt') { rvQuickAdopt(el.dataset.rv); return; }
  if (action === 'rvq-reject') { openInlineReject('rv', Number(el.dataset.rv)); return; }
  if (action === 'rvq-reject-ok') { rvQuickReject(el.dataset.rv); return; }
  if (action === 'rvq-reject-cancel') { closeInlineReject('rv'); return; }
  if (action === 'rvq-reject-keep') { return; }
  if (action === 'sgsq-adopt') { sgsQuickAdopt(el.dataset.sgs); return; }
  if (action === 'sgsq-reject') { openInlineReject('sgs', Number(el.dataset.sgs)); return; }
  if (action === 'sgsq-reject-ok') { sgsQuickReject(el.dataset.sgs); return; }
  if (action === 'sgsq-reject-cancel') { closeInlineReject('sgs'); return; }
  if (action === 'sgsq-confirm-cancel') { state.sgsQuickConfirm = null; renderView(); return; }
  if (action === 'sgsq-audit') { sgsQuickAudit(el.dataset.sgs); return; }
  if (action === 'sgsq-why') {
    state.sgsId = Number(el.dataset.sgs);
    state.sgsTab = 'audit';
    state.sgsConfirm = null;
    state.sgsRejectIn = null;
    state.sgsQuickConfirm = null;
    renderView();
    syncRvHash();
    return;
  }
  if (action === 'sgsq-reject-keep' || action === 'sgsq-keep') { return; }
  if (action === 'expq-approve') { expQuickApprove(el.dataset.exp); return; }
  if (action === 'expq-reject') { openInlineReject('exp', el.dataset.exp); return; }
  if (action === 'expq-reject-ok') { expQuickReject(el.dataset.exp); return; }
  if (action === 'expq-reject-cancel') { closeInlineReject('exp'); return; }
  if (action === 'expq-confirm-cancel') { state.expQuickConfirm = null; renderView(); return; }
  if (action === 'expq-reject-keep' || action === 'expq-keep') { return; }
  if (action === 'fc-backtest') { location.hash = '#/system/factors'; return; }
  if (action === 'fc-propose') { proposeFactor(el.dataset.fc); return; }
  if (action === 'exp-select') { selectExp(el.dataset.exp); return; }
  if (action === 'exp-tab') { state.expTab2 = el.dataset.tab; refreshExpDetail(); return; }
  if (action === 'exp-tab-main') { state.expTab = el.dataset.t; state.expConfirm = null; renderView(); syncExpHash(); return; }
  if (action === 'exp-stage') { state.expStage = el.dataset.s; renderView(); syncExpHash(); return; }
  if (action === 'exp-cancel') { state.expConfirm = null; refreshExpDetail(); return; }
  if (action === 'exp-approve') { state.expConfirm = 'approve-' + el.dataset.exp; refreshExpDetail(); return; }
  if (action === 'exp-approve-ok') { approveExperience(el.dataset.exp); return; }
  if (action === 'exp-reject') { state.expConfirm = 'reject-' + el.dataset.exp; refreshExpDetail(); const t2 = $('#exp-reason'); if (t2) t2.focus(); return; }
  if (action === 'exp-reject-ok') { rejectExperience(el.dataset.exp); return; }
  if (action === 'exp-expire') { state.expConfirm = 'expire-' + el.dataset.exp; refreshExpDetail(); return; }
  if (action === 'exp-expire-ok') { expireExperience(el.dataset.exp); return; }
  if (action === 'exp-rollback') { state.expConfirm = 'rollback-' + el.dataset.exp; refreshExpDetail(); const t3 = $('#exp-reason'); if (t3) t3.focus(); return; }
  if (action === 'exp-rollback-ok') { rollbackExperience(el.dataset.exp); return; }
  if (action === 'exp-to-rule') {
    const ex = expById(el.dataset.exp);
    if (ex) ex.logs.unshift({ time: '刚刚', who: '你转成规则建议', text: '高影响经验已生成规则建议，进入 AI 审计队列。' });
    toast('已转成规则建议', '高影响经验不能直接改交易行为，先送 AI 审计，审计通过后还需要人工确认。', 'ok', { label: '去规则审计', fn: () => { location.hash = '#/system/rules'; } });
    refreshExpDetail();
    return;
  }
  if (action === 'rule-bucket') {
    state.ruleBucket = el.dataset.bucket;
    state.pendingAction = null;
    state.ruleChecked = [];
    state.batchAction = null;
    renderView();
    syncRuleHash();
    return;
  }
  if (action === 'quick-approve') { selectRule(id); startAction('approve', id); return; }
  if (action === 'quick-reject') { selectRule(id); startAction('reject', id); return; }
  if (action === 'batch-start') { batchStart(el.dataset.kind); return; }
  if (action === 'batch-confirm') { batchConfirm(el.dataset.kind); return; }
  if (action === 'batch-cancel') { batchCancel(); return; }
  if (action === 'batch-clear') { state.ruleChecked = []; state.batchAction = null; refreshRuleList(); $('#batch-slot').innerHTML = batchBarHtml(); return; }
  if (action === 'export-audit') { exportAudit(); return; }
  if (action === 'rule-clear') { state.ruleQuery = ''; state.ruleAgent = ''; state.ruleType = ''; renderView(); return; }
  if (action === 'rule-detail-tab') { state.ruleDetailTab = el.dataset.tab; refreshRuleDetail(); return; }
  if (action === 'act-approve') { startAction('approve', id); return; }
  if (action === 'act-reject') { startAction('reject', id); return; }
  if (action === 'act-rollback') { startAction('rollback', id); return; }
  if (action === 'act-confirm') { confirmAction(el.dataset.kind, id); return; }
  if (action === 'act-cancel') { state.pendingAction = null; refreshRuleDetail(); return; }
  if (action === 'act-reaudit') { reauditRule(id); return; }
  if (action === 'act-rereview') { rereviewRule(id); return; }
  if (action === 'audit-all') { runIncrementalAudit(); return; }
  if (action === 'factor-offline') { state.factorConfirm = el.dataset.fid; renderView(); return; }
  if (action === 'factor-cancel') { state.factorConfirm = null; renderView(); return; }
  if (action === 'factor-offline-confirm') {
    const reasonEl = $('#factor-reason');
    const reason = reasonEl ? reasonEl.value.trim() : '';
    if (!reason) { toast('原因必填', '下线原因需要写入审计记录。', 'warn'); return; }
    offlineFactor(el.dataset.fid, reason);
    return;
  }
  if (action === 'factor-keep') { keepFactor(el.dataset.fid); return; }
  if (action === 'factor-detail') { openDrawer('factor', id); return; }
  if (action === 'agent-detail') { openDrawer('agent', id); return; }
  if (action === 'collab-query') { collabQuery(); return; }
});

document.addEventListener('keydown', (e) => {
  const palette = $('#palette');
  if (palette && !palette.hidden) {
    const items = renderPalette($('#palette-input').value);
    if (e.key === 'Escape') { closePalette(); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); state.paletteIndex = Math.min(state.paletteIndex + 1, Math.max(items.length - 1, 0)); renderPalette($('#palette-input').value); return; }
    if (e.key === 'ArrowUp') { e.preventDefault(); state.paletteIndex = Math.max(state.paletteIndex - 1, 0); renderPalette($('#palette-input').value); return; }
    if (e.key === 'Enter' && items[state.paletteIndex]) { location.hash = items[state.paletteIndex].path; closePalette(); return; }
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    openPalette();
    return;
  }
  if (e.key === 'Escape') {
    closeDrawer();
    closePalette();
    return;
  }
  if (state.route.startsWith('#/system/rules') && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    if (e.target instanceof Element && e.target.matches('input, textarea, select')) return;
    const list = filteredRules();
    if (!list.length) return;
    e.preventDefault();
    const idx = list.findIndex((r) => r.id === state.selectedRuleId);
    const step = e.key === 'ArrowDown' ? 1 : -1;
    const next = list[Math.max(0, Math.min(list.length - 1, (idx < 0 ? 0 : idx + step)))];
    selectRule(next.id);
    const rowEl = $('.rule-row[data-id="' + next.id + '"]');
    if (rowEl) rowEl.scrollIntoView({ block: 'nearest' });
    return;
  }
  if (state.route === '#/candidates' && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    if (e.target instanceof Element && e.target.matches('input, textarea, select')) return;
    const list = filteredCandidates();
    if (!list.length) return;
    e.preventDefault();
    const idx = list.findIndex((c) => c.stock_code === state.candId);
    const step = e.key === 'ArrowDown' ? 1 : -1;
    const next = list[Math.max(0, Math.min(list.length - 1, (idx < 0 ? 0 : idx + step)))];
    selectCand(next.stock_code);
    const rowEl = $('.cp-row[data-cand="' + next.stock_code + '"]');
    if (rowEl) rowEl.scrollIntoView({ block: 'nearest' });
    return;
  }
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('.rule-row[role="button"]')) {
    e.preventDefault();
    selectRule(e.target.dataset.id);
  }
  if (state.route === '#/reviews' && state.rvBoard === 'sug' && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    if (e.target instanceof Element && e.target.matches('input, textarea, select')) return;
    const list = filteredSugs();
    if (!list.length) return;
    e.preventDefault();
    const idx = list.findIndex((s) => s.id === state.sgsId);
    const step = e.key === 'ArrowDown' ? 1 : -1;
    const next = list[Math.max(0, Math.min(list.length - 1, (idx < 0 ? 0 : idx + step)))];
    selectSug(next.id);
    const rowEl = $('.sgs-row[data-sgs="' + next.id + '"]');
    if (rowEl) rowEl.scrollIntoView({ block: 'nearest' });
    return;
  }
  if (state.route === '#/reviews' && state.rvBoard === 'list' && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    if (e.target instanceof Element && e.target.matches('input, textarea, select')) return;
    const list = filteredReviews();
    if (!list.length) return;
    e.preventDefault();
    const idx = list.findIndex((r) => r.id === state.rvId);
    const step = e.key === 'ArrowDown' ? 1 : -1;
    const next = list[Math.max(0, Math.min(list.length - 1, (idx < 0 ? 0 : idx + step)))];
    selectReview(next.id);
    const rowEl = $('.rv-row[data-rv="' + next.id + '"]');
    if (rowEl) rowEl.scrollIntoView({ block: 'nearest' });
    return;
  }
  if (state.route === '#/experience' && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    if (e.target instanceof Element && e.target.matches('input, textarea, select')) return;
    const list = filteredExperiences();
    if (!list.length) return;
    e.preventDefault();
    const idx = list.findIndex((x) => x.id === state.expId);
    const step = e.key === 'ArrowDown' ? 1 : -1;
    const next = list[Math.max(0, Math.min(list.length - 1, (idx < 0 ? 0 : idx + step)))];
    selectExp(next.id);
    const rowEl = $('.ex-row[data-exp="' + next.id + '"]');
    if (rowEl) rowEl.scrollIntoView({ block: 'nearest' });
    return;
  }
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('.cp-row[role="button"]')) {
    e.preventDefault();
    if (e.target.dataset.rv) selectReview(e.target.dataset.rv);
    else if (e.target.dataset.exp) selectExp(e.target.dataset.exp);
    else if (e.target.dataset.sgs) selectSug(e.target.dataset.sgs);
    else selectCand(e.target.dataset.cand);
  }
});

$('#palette-input').addEventListener('input', (e) => {
  state.paletteIndex = 0;
  renderPalette(e.target.value);
});
$('#palette').addEventListener('click', (e) => {
  if (e.target === $('#palette')) closePalette();
});

window.addEventListener('hashchange', () => {
  parseRoute();
  closeDrawer();
  state.pendingAction = null;
  state.factorConfirm = null;
  state.ruleChecked = [];
  state.batchAction = null;
  if (state.route === '#/system/rules' && state.ruleBucket === 'todo') {
    // 保持用户最近选择的队列
  }
  if (state.route === '#/system/overview') {
    // 总览不强制切换规则队列
  }
  refreshAll();
  window.scrollTo({ top: 0 });
});

/* ---------- 启动 ---------- */
function init() {
  hydrateIcons(document);
  if (!location.hash) location.hash = '#/system/overview';
  parseRoute();
  renderSidebar();
  renderCrumb();
  renderView();
}

init();
