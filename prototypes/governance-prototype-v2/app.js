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
    link: '', linkLabel: ''
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
  // 工作台总览：本地展开态与「今天先放过」勾记，只影响本页列表，不改任何业务数据
  woOnlyTodo: false,
  woReveal: { schedule: false, tasks: false },
  woDone: {},
  woFeed: [],
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
  plStatus: '全部',
  plDate: '',
  plGrade: '全部评级',
  plSource: '全部来源',
  plExpand: {},
  plConfirm: null,
  plCode: '',
  plGen: '',
  plNewOpen: false,
  plBusy: false,
  plBusyId: null,
  plGapOpen: false,
  plNoteOpen: false,
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
  holdings: null,
  exited: null,
  hdAccount: null,
  hdView: 'all',
  hdId: 2071,
  hdTab: 'concl',
  hdKlineOpen: false,
  hdForm: null,
  hdTradeDrafts: {},
  hdArchiveId: null,
  hdHistOpen: true,
  hdNewPending: null,
  hdOcrDone: false,
  hdOcrRows: null,
  paper: null,
  paperSeq: null,
  ppAcc: 901,
  ppView: 'current',
  ppTab: 'positions',
  ppPos: '603501',
  ppCtx: null,
  ppFilter: '',
  ppForm: null,
  ppKline: false,
  miDate: null,
  miBoard: 'regime',
  miHorizon: 't1',
  miChainMode: 'chain',
  miExpand: {},
  miSector: null,
  miDrawerPending: false,
  miIntelBusy: null,
  miRuns: null,
  miLog: null,
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
      { path: '#/paper', label: 'AI 模拟操盘', icon: 'agent' },
      { path: '#/alerts', label: '告警日志', icon: 'bell' }
    ]
  },
  {
    group: '研究', items: [
      { path: '#/market-intel', label: '市场研判', icon: 'compass' },
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
      { path: '#/experience', label: '经验沉淀', icon: 'layers' }
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
  '#/alerts': { title: '告警日志', desc: '下一批设计：按严重度分组，支持一键进入对应持仓或规则。', scope: ['严重度分组与已读状态', '告警 → 持仓 / 规则 / 复盘 的深链', '保留原始 payload 折叠查看'] },
  '#/scores': { title: '评分报告', desc: '下一批设计：评分表 + 详情抽屉，采纳状态更清晰。', scope: ['A/B/C 分级筛选', '六因子解释与风险计数', '一键去建仓计划'] },
  '#/agent-chat': { title: 'Agent 对话', desc: '下一批设计：保留看板化对话，接入治理留痕。', scope: ['任务型对话与普通问答分流', '任务状态与结果卡片', '留痕与治理深链'] }
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
  if (path === '#/plans') {
    const pp = new URLSearchParams(qi < 0 ? '' : raw.slice(qi + 1));
    const labels = ['全部'].concat(PL_STATUS_ORDER.map((k) => PL_STATUS_LABEL[k]));
    if (pp.get('status') && labels.indexOf(pp.get('status')) >= 0) state.plStatus = pp.get('status');
    const dl = plDates();
    if (pp.get('date') && (pp.get('date') === '全部日期' || dl.indexOf(pp.get('date')) >= 0)) state.plDate = pp.get('date');
    if (pp.get('grade') && ['全部评级', 'A', 'B', 'C', '未评级'].indexOf(pp.get('grade')) >= 0) state.plGrade = pp.get('grade');
    if (pp.get('source') && ['全部来源', 'candidate', 'manual', '每日候选池', '手动生成'].indexOf(pp.get('source')) >= 0) {
      state.plSource = pp.get('source') === '每日候选池' ? 'candidate' : pp.get('source') === '手动生成' ? 'manual' : pp.get('source');
    }
    if (pp.get('code')) state.plCode = pp.get('code');
    if (pp.get('gen')) { state.plGen = pp.get('gen'); state.plNewOpen = true; state.plDate = ''; }
    (pp.get('id') || '').split(',').filter(Boolean).forEach((x) => {
      const row = PLANS.find((q) => String(q.id) === x);
      if (row) state.plExpand[row.id] = true;
    });
  }
  if (path === '#/candidates') {
    const params = new URLSearchParams(qi < 0 ? '' : raw.slice(qi + 1));
    const id = params.get('id');
    if (id && CANDIDATE_POOL.some((c) => c.stock_code === id)) { state.candId = id; state.candMode = 'today'; }
    const d = params.get('date');
    if (d && CAND_BATCHES.some((b) => b.date === d)) { state.candBatch = d; state.candMode = 'history'; }
    if (params.get('mode') === 'today') state.candMode = 'today';
  }
  if (path === '#/holdings') {
    const hp = new URLSearchParams(qi < 0 ? '' : raw.slice(qi + 1));
    const hid = hp.get('id');
    if (hid && hdData().some((r) => String(r.id) === String(hid))) {
      state.hdId = Number(hid);
      if (hp.get('view') === 'exited') state.hdView = 'all';
    }
    const hvw = hp.get('view');
    if (hvw && HD_VIEWS.some((v) => v[0] === hvw)) state.hdView = hvw;
    const htb = hp.get('tab');
    if (htb && ['concl', 'basis', 'ops', 'risk'].indexOf(htb) >= 0) state.hdTab = htb;
    state.hdForm = null;
  }
  if (path === '#/paper') {
    const pp = new URLSearchParams(qi < 0 ? '' : raw.slice(qi + 1));
    const acc = pp.get('acc');
    if (acc && ppData().some((a) => String(a.id) === String(acc))) {
      state.ppAcc = Number(acc);
      state.ppView = ppData().filter((a) => String(a.id) === String(acc))[0].status === 'archived' ? 'archived' : 'current';
    }
    const pvw = pp.get('view');
    if (pvw && ['current', 'archived'].indexOf(pvw) >= 0) state.ppView = pvw;
    const ptb = pp.get('tab');
    if (ptb && PP_TABS.some((t) => t[0] === ptb)) state.ppTab = ptb;
    const pos = pp.get('pos');
    if (pos && ppAcc().universe[pos]) state.ppPos = pos;
    const pfl = pp.get('filter');
    if (pfl && PP_FILTERS.some((f) => f[0] === pfl)) state.ppFilter = pfl;
    const ctx = pp.get('ctx');
    if (ctx && ppAcc().contexts.some((c) => String(c.id) === String(ctx))) {
      state.ppCtx = Number(ctx);
      state.ppTab = 'contexts';
    }
    state.ppForm = null;
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
  if (path === '#/market-intel') {
    const mp = new URLSearchParams(qi < 0 ? '' : raw.slice(qi + 1));
    const md = mp.get('date');
    if (md && miIdx(md) >= 0) state.miDate = md;
    const mb = mp.get('board');
    if (mb && MI_BOARDS.some((b) => b[0] === mb)) state.miBoard = mb;
    const mh = mp.get('h');
    if (mh && ['t1', 't3', 't5'].indexOf(mh) >= 0) state.miHorizon = mh;
    const ms = mp.get('sector');
    if (ms) { state.miSector = ms; state.miDrawerPending = true; }
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
      kind === 'approve' ? '只有 AI 审核通过的建议才能批量采纳，采纳即写入规则表；未通过的可批量驳回或重新审核。' : '请勾选待处理的规则。',
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
/* ---------- 工作台总览 ----------
   本页不另存一份业务数据：待办、账户、产出全部现算自各模块自己的种子与函数，
   所以同一个数字在总览和那个页面必然一致（生产同理：只调既有只读接口，不新建聚合口径）。
   本页独有的两张事实表：WO_JOBS（当天定时任务时刻表，生产来自定时任务执行留痕）
   与 WO_TASKQ（后台任务队列里非规则审核的部分，生产来自任务队列接口）。 */
const WO_TODAY = NOW_REF.getFullYear() + '-' + String(NOW_REF.getMonth() + 1).padStart(2, '0') + '-' + String(NOW_REF.getDate()).padStart(2, '0');
const WO_AT = String(NOW_REF.getHours()).padStart(2, '0') + ':' + String(NOW_REF.getMinutes()).padStart(2, '0');
const WO_MARKET_AMOUNT = '2.11';   // 两市成交额（万亿元）：只在总览出现，其余数字都来自各模块
const WO_INDEX_REST = [            // 上证指数取自持仓账户快照（state.hdAccount.index），此处只列其余两项
  { name: '深证成指', value: 12841.60, pct: 0.71 },
  { name: '创业板指', value: 2688.35, pct: 1.05 }
];

/* 当天定时任务时刻表（顺序 = 计划时刻，不按完成时间排，方便对着表核对「今天该跑的跑了吗」）。
   status: done 已执行 / failed 执行失败 / skip 本轮无事可做 / soon 还没到点
   effect: 这一格失守会影响哪个页面的哪个数字（没影响就不写）
   manual: queue 就地提交补跑任务（后端有对应接口）/ page 只能去那一页点它自己的按钮
           / derive 打开页面就算（纯计算通道，没有任务）/ none 这一轮补不回来 */
/* 当天定时任务时刻表 —— 行集合与计划时刻照抄生产注册表 backend/app/scheduler/jobs.py
   （工作日 mon-fri；monitor 每 MONITOR_INTERVAL_MINUTES=3 分钟、red_line 每 10 分钟落在 7/17/…/57 分，
    与 take_profit 刻意错峰，避免同刻并发取行情把进程打崩）。顺序 = 计划时刻，不按完成时间排，
    方便对着表核对「今天该跑的跑了吗」。
   status: done 已执行 / failed 执行失败 / skip 本轮无事可做 / soon 还没到点
   effect: 这一格失守会影响哪个页面的哪个数字（没影响就不写）
   manual: queue 就地提交补跑任务（_TASK_KINDS 里真有这个 kind）/ page 只能去那一页点它自己的按钮
           / derive 打开页面就算（纯计算通道，没有任务）/ none 这一轮补不回来 */
const WO_JOBS = [
  { id: 'experience_worker', kind: 'experience_worker', name: '经验沉淀识别', at: '每天 02:00 主跑', status: 'done',
    run: '02:00:33', out: '今晨把积压的复盘识别成 2 条经验候选',
    effect: '今天新写的复盘要等下一轮（另有每 30 分钟探针看积压）', nav: '#/experience', manual: 'queue' },
  { id: 'audit_pending', kind: 'audit_pending', name: '建议辩证审核', at: '每天 03:30 批量', status: 'done',
    run: '03:31:02', out: '批量审核 12 条闭环建议：通过 5 条、未过 7 条（每条都附一段具体反例）',
    effect: '未过的会自动触发一次「复盘建议重思考」重出一版；通过的也不会自己生效——要你在队列点采纳，才写进规则表并注入全部 Agent',
    nav: '#/reviews?board=sug', manual: 'queue' },
  { id: 'monitor', kind: 'monitor_all', name: '盘中持仓监控', at: '盘中每 3 分钟（只跑 09:30-11:30 / 13:00-15:00）',
    status: 'done', run: '14:55:31', out: '3 只要处理（1 只踩止损红线）',
    effect: '每只持仓的判定时刻来自这一轮；15:00-15:30 只做收盘校验，不再刷新价',
    nav: '#/holdings?view=todo', manual: 'queue' },
  { id: 'paper_monitor', name: 'AI 模拟盘中监控', at: '盘中每 5 分钟（模拟仓独立）', status: 'done', run: '15:03:18',
    out: '模拟仓研究上下文已刷新', nav: '#/paper?acc=901&tab=positions', manual: 'page' },
  { id: 'take_profit', name: '止盈止损确定性通道', at: '盘中每 3 分钟，比监控错峰 2 分钟', status: 'done',
    run: '14:57:06', out: '纯计算，不调用模型', effect: '跌破止损、到达止盈走这条通道直接判定',
    nav: '#/holdings?view=all', manual: 'derive' },
  { id: 'quote_snapshot_refresh', name: '持仓价快照刷新', at: '盘中每 5 分钟（09:02-15:57）', status: 'done',
    run: '14:56:12', out: '最后一次成功 14:56:12，之后批量行情接口再没返回过',
    effect: '持仓页的现价、浮亏全部停在这一刻', nav: '#/holdings?view=all', manual: 'none' },
  { id: 'sector_refresh', name: '板块快照刷新', at: '盘中每 5 分钟（09:01-15:56）', status: 'done', run: '15:56:04',
    out: '全板块成交额、涨跌家数已落库', nav: '#/market-intel?board=volume', manual: 'none' },
  { id: 'portfolio_sentinel', kind: 'portfolio_sentinel', name: '组合哨兵巡检', at: '盘中每 10 分钟（04/14/…/54 分）',
    status: 'done', run: '16:04:11', out: '3 条：止损红线、总仓位超限、单票超限',
    nav: '#/holdings?view=all', manual: 'queue' },
  { id: 'red_line', name: '持仓红线扫描', at: '盘中每 10 分钟（07/17/…/57 分）', status: 'failed', run: '15:57:31',
    reason: '15:07 起连续 6 轮失败：行情批量接口 6 秒没返回（DataSourceError），15:57 是今天最后一轮',
    effect: '红线最后一次成功判定是 14:57。下面那只跌破止损的浮亏用的是 14:56:12 的价，之后的波动没算进来',
    nav: '#/holdings?id=2064', manual: 'none' },
  { id: 'pre_market_screen', name: '盘前快筛', at: '09:25（集合竞价撮合完成后）', status: 'done', run: '09:25:06',
    out: '盘前候选清单已生成（用的是上一交易日 16:10 的候选）', nav: '#/candidates', manual: 'none' },
  { id: 'overnight_factor_verify', name: '美股隔夜因子校验', at: '09:35', status: 'done', run: '09:35:22',
    out: '隔夜缺口已回填台账', effect: '今早的行情结构识别用上了这份数据',
    nav: '#/market-intel?board=basis', manual: 'none' },
  { id: 'distribution_phase', name: '派发期判定', at: '15:30', status: 'done', run: '15:30:22',
    out: '未进派发期：今天上涨 3320 家 / 下跌 1420 家', nav: '#/market-intel?board=basis', manual: 'none' },
  { id: 'market_accuracy', name: '市况次日指数回填', at: '15:30', status: 'done', run: '15:30:41',
    out: '11-13 的展望对上了 11-16 的实际走势', nav: '#/market-intel?board=regime', manual: 'page' },
  { id: 'sector_daily', name: '板块轮动日快照', at: '15:35', status: 'done', run: '15:35:12',
    out: '今日领涨：CPO光模块、液冷服务器、算力租赁', nav: '#/market-intel?board=rotation', manual: 'page' },
  { id: 'sector_regime', name: '行情结构识别', at: '15:40', status: 'done', run: '15:40:08',
    out: '主线行情 · 确认段（CPO光模块连续 4 日领涨）', nav: '#/market-intel?board=regime', manual: 'page' },
  { id: 'sector_forward', name: '板块前瞻预测', at: '15:45', status: 'done', run: '15:45:33',
    out: 'T+1 / T+3 / T+5 三档预测已落库', nav: '#/market-intel?board=regime', manual: 'page' },
  { id: 'sector_next_hot', name: '下一个风口预测', at: '15:50', status: 'done', run: '15:50:19',
    nav: '#/market-intel?board=rotation', manual: 'none' },
  { id: 'track_verify', kind: 'track_verify', name: '候选池 T+N 验证', at: '16:00', status: 'done', run: '16:00:44',
    out: '历史批次的 T+1/T+3/T+5 收益已补记', nav: '#/reviews?board=track', manual: 'queue' },
  { id: 'forward_view_fill', name: '前瞻 T+5 回填', at: '16:00', status: 'skip', run: '16:00:46',
    reason: '11-13 那批今天只到 T+1（11-14、11-15 休市），要到 11-20 才满 5 个交易日',
    effect: '市场研判页的预测准确率仍按 11-13 之前的样本算，今天不更新',
    nav: '#/market-intel?board=regime', manual: 'page' },
  { id: 'sector_forecast_verify', kind: 'sector_forecast_verify', name: '前瞻验证回填', at: '16:05', status: 'done',
    run: '16:05:22', out: '上一批预测已用真实板块快照校验', nav: '#/market-intel?board=regime', manual: 'queue' },
  { id: 'daily_discover', kind: 'daily_pipeline', name: '每日潜力股挖掘', at: '16:10', status: 'done', run: '16:10:42',
    out: '候选 8 只 · 可建仓 3 只', effect: '评分 B 级以上的自动出建仓计划：今天 2 份（都算成 0 股，见「要我处理」）',
    nav: '#/candidates', manual: 'queue' },
  { id: 'market_intel', kind: 'market_intel', name: '市场研判', at: '16:20', status: 'done', run: '16:20:41',
    out: '主线确认段 · 可分批参与已证明业绩的环节', nav: '#/market-intel?date=' + WO_TODAY, manual: 'queue' },
  { id: 'kline_ingest', name: '本地日线增量', at: '16:25', status: 'done', run: '16:25:31',
    out: '当日全市场日线无缺数', effect: '评分和建仓用的就是这份收盘价', nav: null, manual: 'none' },
  { id: 'paper_execution', name: 'AI 模拟复盘审核', at: '16:35', status: 'done', run: '16:35:12',
    out: '平仓 1 笔（宁德时代 +1,304.96）· 复盘 3 篇', nav: '#/paper?acc=901&tab=reviews', manual: 'page' },
  { id: 'signal_scan', name: '买卖点信号扫描', at: '16:50', status: 'done', run: '16:50:22',
    out: '信号已写入告警日志', effect: '那一页目前还是占位，还没有读它的地方', nav: '#/alerts', manual: 'none' },
  { id: 'overnight_factor_collect', name: '美股隔夜因子采集', at: '21:30', status: 'soon', run: '',
    reason: '现在 ' + WO_AT + '，还没到点', effect: '今晚采集的隔夜因子，明天 09:35 才校验、才进行情结构',
    nav: '#/market-intel?board=basis', manual: 'none' }
];
const WO_JOBS_NOTE = '没列进来的：游资胜率迭代（16:30）与行业消息雷达（每天 08:00、shadow 回填 16:25）——' +
  '数据链还在跑，但你已经不看这两个页面了；本地日线夜间回补（00:40）、每日 02:00 之外的经验探针（每 30 分钟）、' +
  '前瞻先验校准（周日 04:00）、存储空间维护（周日 05:30）、因子 IC 月度回测（每月 1 日 02:00，' +
  '那 2 条因子失效建议就是它产出的）、龙虎榜 T+1 与飞书日报（默认关闭）、同花顺链路（2026-09-16 已下线）。';


/* 后台任务队列里「非审核」的部分（审核任务的状态跟着建议本身走，见 woRuleTasks） */
/* 本轮审核的提交时刻（生产按 last_audit_id 回查 audit_log.created_at）：没有它就填当前时刻 */
const WO_AUDIT_SUBMIT = { 'RC-1049': '2026-11-16 16:52', 'RC-1038': '2026-11-16 17:04' };

const WO_TASKQ = [
  { id: 'T-1160', kind: 'monitor_all', name: '全量持仓监控', label: '15:58 手动触发', status: 'failed',
    from: '15:58:12', to: '15:58:19', pct: 0, mine: true,
    error: '行情接口超时 DataSourceError —— 与 15:07 起的红线扫描是同一个故障' },
  { id: 'T-1159', kind: 'monitor_all', name: '全量持仓监控', label: '15:31 手动触发', status: 'canceled',
    from: '15:31:02', to: '15:36:44', pct: 40, mine: true,
    error: '你手动取消：卡住 5 分钟没有进度，取消后队列立刻腾出来' },
  { id: 'T-1161', kind: 'daily_pipeline', name: '每日挖掘 · 候选打分', label: '2026-11-16 候选 8 只',
    status: 'done', from: '16:10:42', to: '16:24:18', pct: 100, mine: false, note: '定时任务自动提交' },
  { id: 'T-1158', kind: 'review_rethink', name: '复盘建议重思考', label: '隆基绿能 · 带同板块样本重出一版',
    status: 'done', from: '16:36:12', to: '16:37:02', pct: 100, mine: false,
    note: '首审未过后由审核链路自动提交的重出，不是定时任务' }
];

/* 队列的硬规则：界面文案与交互必须与生产一致，落地时不要改写 */
const WO_TASK_RULES = [
  '队列一次只跑 1 个任务（防外部接口限流）：排队是常态，不代表卡死。',
  '只有失败的任务能点重试：重试复用同一条任务编号，清掉上一次的结果和错误重新入队。',
  '取消只对「排队中 / 执行中」有效：正在跑的那一轮杀不掉，但队列立刻腾出来，且这一轮即使跑完也不允许再写库（页面不会多出半条结果）。',
  '每日挖掘、全量持仓监控超过 35 分钟自动判定失败并释放队列（防卡死占住唯一的执行位）。',
  '同类任务没跑完之前重复提交会被拒（HTTP 409），页面显示「已有同类任务在执行」——这就是重复点击不会跑两遍的原因。',
  '审核只发给还没定论的建议：已审过的条目再点会被拒，要推翻已有结论走「强制采纳 + 写明原因」。'
];

/* 今天动作与发现：上面没列出来的产出（重复标题会自动隐藏，处理完一件这条就消失） */
const WO_FEED_SEED = [
  { t: '16:35', who: 'ai', title: '模拟盘今天平仓 1 笔', body: '宁德时代 +1,304.96（已扣费用）。这是模拟仓，不是你账户里的持仓。', nav: '#/paper?acc=901&tab=executions' },
  { t: '16:10', who: 'ai', title: '挖掘选出 8 只候选，3 只可建仓', body: '韦尔股份 88 分、紫光国微 84 分、航发动力 81 分；另外 3 只「建议关注」、2 只「观察」。', nav: '#/candidates?mode=today' },
  { t: '15:40', who: 'ai', title: '行情结构进入主线确认段', body: 'CPO光模块连续 4 日领涨，60 日箱位中位 70%；但算力租赁只是跟随，独立证据缺失。', nav: '#/market-intel?date=' + WO_TODAY },
  { t: '15:02', who: 'sys', title: '模拟盘放到今天第 3 轮', body: '09:35 那一轮成交后模拟总资产 306,727.96 元（+2.24%），下一轮 2026-11-17 09:33。', nav: '#/paper?acc=901' },
  { t: '10:20', who: 'ai', title: '2 个因子连续 3 个月失效', body: '动量 20 日、换手突增：|IC| < 0.02，样本 n=1820，建议退出每日打分。要你点头才会从打分里摘掉。', nav: '#/system/factors' }
];
/* 持仓块不再单独维护一份数据：全部从 #/holdings 的实时状态算出来，两边永远一致 */
const HD_SEVERITY = { exit: 0, reduce: 1, watch: 2, info: 3, hold: 4 };
const HD_STATE_LABEL = { exit: '红线预警', reduce: '该减', watch: '关注', info: '待补行情', hold: '继续拿' };

function hdPnlPct(r) { return r.price == null ? null : (r.price / r.cost - 1) * 100; }
function woTodayPrefix(h) { return h.today == null ? '还没有行情' : (h.today >= 0 ? '+' : '') + h.today.toFixed(2) + '% 今日'; }
function woTodayCell(h) { return h.today == null
  ? '<span class="mono dim">无行情</span>'
  : '<span class="mono ' + (h.today >= 0 ? 'wo-up' : 'wo-down') + '">' + (h.today >= 0 ? '+' : '') + h.today.toFixed(2) + '%</span>'; }

function woHoldNote(r, v) {
  if (v === 'info') return '这只还没有行情：成本 ' + r.cost.toFixed(2) + '，止损 ' + r.stop.toFixed(2) + '，补上现价才能算红线';
  const pnl = hdPnlPct(r);
  if (v === 'exit') return '现价 ' + r.price.toFixed(2) + ' 已跌破止损红线 ' + r.stop.toFixed(2) + '（成本 ' + r.cost.toFixed(2) + '×0.92）';
  if (r.trail && r.trail.hit) return '浮盈 ' + hdPct(pnl, 1) + '，移动止盈' + r.trail.stage + '，按档减仓';
  if (v === 'reduce') return '浮盈 ' + hdPct(pnl, 1) + '，但单票占总资产 ' + (r.shares * r.price / state.hdAccount.total * 100).toFixed(1) + '%，超过 ' + r.targetPct + '% 上限';
  if (v === 'watch') return pnl < 0
    ? '跌破成本，距止损 ' + r.stop.toFixed(2) + ' 只差 ' + ((r.price - r.stop) / r.price * 100).toFixed(1) + '%，到价就走'
    : '浮盈 ' + hdPct(pnl, 1) + '，红线都没踩，破 ' + r.stop.toFixed(2) + ' 才动';
  return '浮盈 ' + hdPct(pnl, 1) + '，四条红线都没踩，按计划拿着';
}

function woPlanBody(r) {
  const v = hdVerdict(r);
  const t = r.trail;
  if (v === 'info') return '先补齐行情才能算止盈止损；当前成本 ' + r.cost.toFixed(2) + '，止损 ' + r.stop.toFixed(2) + '。';
  if (v === 'exit') return '止损 ' + r.stop.toFixed(2) + ' = 成本 ' + r.cost.toFixed(2) + '×0.92，永久红线，已跌破，不上移。';
  if (t && t.hit) return '移动止盈' + t.stage + '，按档先减一部分；下一档 ' + r.tp.toFixed(2) + '，止损已上移至 ' + r.stop.toFixed(2) + '。';
  if (v === 'reduce') return '先减一档把单票占比压回 ' + r.targetPct + '% 以内；' + (t ? t.next + '。' : '止损 ' + r.stop.toFixed(2) + '。');
  if (v === 'watch') return '未破 ' + r.stop.toFixed(2) + ' 之前不动；反弹到 ' + r.tp.toFixed(2) + ' 再谈止盈。';
  return (t ? t.next + '；' : '') + '止盈 ' + r.tp.toFixed(2) + '，止损 ' + r.stop.toFixed(2) + '。';
}

function woHoldings() {
  const rows = hdData().slice().sort((a, b) => {
    const d = HD_SEVERITY[hdVerdict(a)] - HD_SEVERITY[hdVerdict(b)];
    return d !== 0 ? d : (b.shares * (b.price || 0)) - (a.shares * (a.price || 0));
  });
  const pnl = hdTodayPnl();
  const total = state.hdAccount.total;
  return {
    rows: rows.slice(0, 4).map((r) => ({
      id: r.id, code: r.code, name: r.name, today: r.today,
      state: HD_STATE_LABEL[hdVerdict(r)], note: woHoldNote(r, hdVerdict(r))
    })),
    plans: rows.slice(0, 4).map((r) => ({ id: r.id, code: r.code, name: r.name, body: woPlanBody(r) })),
    summary: {
      mv: hdMoney(hdTotalMv()),
      total: (total / 10000).toFixed(1) + ' 万',
      share: hdTotalShare().toFixed(1) + '%',
      todayPnl: Math.round(pnl),
      todayPct: pnl / total * 100,
      count: rows.length,
      redline: rows.filter((r) => hdVerdict(r) === 'exit').length,
      todo: hdTodo().length
    }
  };
}

/* 审核跑完：建议转入「等你决定」，本页不替你点头（点采纳才会写进规则表；与规则页 reauditRule 同一条时间线） */
function woAuditFinish(t) {
  const r = state.rules.filter(function (x) { return x.id === t.auditId; })[0];
  if (!r || r.audit !== 'auditing') return;
  r.audit = 'pass';
  r.timeline = r.timeline || [];
  r.timeline.push({ time: WO_AT, title: 'AI 审核通过', actor: 'ai',
    body: '第 ' + (r.round || 1) + ' 轮审核跑完，判定通过，已放进「等你决定」。', tone: 'ok' });
  state.woFeed.unshift({ mine: false, who: 'ai', t: WO_AT.slice(11),
    title: '建议 ' + r.id + ' 审核完成',
    body: r.name + '：AI 审核通过，等你采纳才会写进规则表并注入全部 Agent。队列腾出来了，下一条自动开始。',
    nav: '#/system/rules?bucket=todo&id=' + r.id });
  if (state.route !== '#/overview') return;
  refreshAll();
  toast('审核完成', r.name + ' ' + r.id + ' 已转入「等你决定」；采纳后才会生成规则变更留痕。', 'success');
}

/* 队列视图 = 建议审核任务（状态跟随建议本身）+ 其他后台任务。
   同一条建议同一轮只建一个对象：整页重绘不会把进度清零，也不会两条同时跑（队列一次只跑 1 个）。 */
const woAuditTasks = {};
function woRuleTasks() {
  return state.rules.filter(function (r) { return r.audit === 'auditing'; }).map(function (r) {
    const k = r.id + '#' + (r.round || 1);
    if (!woAuditTasks[k]) {
      woAuditTasks[k] = {
        id: 'AUDIT-' + r.id, kind: 'audit_one', name: '单条建议辩证审核',
        label: r.name + ' · ' + r.id + '（第 ' + (r.round || 1) + ' 轮）',
        status: 'pending', pct: 0, mine: false, seq: ++woSeq, ms: 22000,
        from: WO_AUDIT_SUBMIT[r.id] || WO_AT, auditId: r.id,
        nav: '#/system/rules?bucket=auditing&id=' + r.id, navLabel: '看这条建议',
        _done: function () {
          return { txt: '第 ' + (r.round || 1) + ' 轮审核完成：通过，等你在队列点采纳',
            nav: '#/system/rules?bucket=todo&id=' + r.id, label: '去看结论' };
        },
        _after: woAuditFinish
      };
    }
    return woAuditTasks[k];
  });
}
function woAllTasks() { return woRuleTasks().concat(WO_TASKQ); }
function woTaskById(id) {
  const all = woAllTasks();
  for (let i = 0; i < all.length; i++) { if (all[i].id === id) return all[i]; }
  return null;
}
function woTaskLabel(status) {
  return status === 'running' ? '执行中' : status === 'pending' ? '排队中'
    : status === 'failed' ? '失败' : status === 'canceled' ? '已取消' : '完成';
}
function woTaskTag(status) {
  return tag(woTaskLabel(status), status === 'running' ? 'blue' : status === 'pending' ? 'gold'
    : status === 'failed' ? 'red' : status === 'canceled' ? 'mute' : 'green');
}
function woRunningCount() { return woAllTasks().filter((t) => t.status === 'running').length; }
function woQueuedCount() { return woAllTasks().filter((t) => t.status === 'pending').length; }

/* 进度只改 DOM，不整页重绘：正在读的那一行不会跳 */
let woTimer = null;
function woPaintProgress() {
  woAllTasks().forEach(function (t) {
    if (t.status !== 'running' || !t._started) return;
    const bar = document.getElementById('wo-bar-' + t.id);
    const val = document.getElementById('wo-pct-' + t.id);
    if (!bar || !val) return;
    const pct = Math.min(96, Math.round((Date.now() - t._started) / (t.ms || 5000) * 100));
    bar.style.width = pct + '%';
    val.textContent = pct + '%';
  });
}
function woEnsureTicker() {
  if (woTimer) return;
  woTimer = setInterval(function () {
    if (state.route !== '#/overview') { clearInterval(woTimer); woTimer = null; return; }
    const tasks = woAllTasks();
    const running = tasks.filter((t) => t.status === 'running');
    if (!running.length) {
      /* 队列一次只跑一个：前面腾空了，排队中的最早一条才开始 */
      const queued = tasks.filter((t) => t.status === 'pending').sort((a, b) => a.seq - b.seq);
      if (!queued.length) { clearInterval(woTimer); woTimer = null; return; }
      woRunTask(queued[0], queued[0].ms || 4200, queued[0]._done);
      renderView();
      return;
    }
    woPaintProgress();
  }, 400);
}
function woRunTask(t, ms, doneFn) {
  t.status = 'running';
  t.pct = 4;
  t.ms = ms;
  t._started = Date.now();
  setTimeout(function () {
    t._started = null;
    t.status = 'done';
    t.pct = 100;
    const extra = doneFn ? doneFn(t) : null;
    if (extra) { t.result = extra.txt; t.refNav = extra.nav; t.refLabel = extra.label; }
    if (t._after) t._after(t);
    else if (state.route === '#/overview') renderView();
  }, ms);
  woEnsureTicker();
}
let woSeq = 0;
function woEnqueue(kind, name, label, ms, doneFn) {
  const t = { id: 'T-' + (1200 + (++woSeq)), kind: kind, name: name, label: label,
    status: 'pending', from: WO_AT, pct: 0, mine: true, seq: woSeq, ms: ms, _done: doneFn };
  WO_TASKQ.unshift(t);
  state.woFeed.unshift({ mine: true, who: 'you', t: WO_AT, name: name,
    title: name + ' · 已提交后台', body: label + ' · 队列一次只跑一个，跑完这一行自己更新',
    nav: '#/overview' });
  woEnsureTicker();
  return t;
}

/* 就地补跑定时任务：只开放后端确实有接口的两项（每日挖掘、全量持仓监控） */
function woRerunJob(j) {
  const dup = woAllTasks().filter(function (t) {
    return t.kind === j.kind && (t.status === 'running' || t.status === 'pending');
  });
  if (dup.length) {
    toast('已有同类任务在跑', '任务 ' + dup[0].id + ' 正在' + woTaskLabel(dup[0].status) +
      '。同类任务没跑完之前不能再提交（后端返回 409），所以重复点也不会跑两遍。', 'warn');
    return;
  }
  const t = woEnqueue(j.kind, j.name, '手动补跑（总览 ' + WO_AT + '）', 4200, function () {
    return { txt: j.out || '已按当前口径重算，没有改任何规则或阈值', nav: j.nav, label: '看结果' };
  });
  renderView();
  toast('补跑任务已提交', '队列一次只跑 1 个任务：' +
    (woAheadOf(t) ? '前面还有 ' + woAheadOf(t) + ' 个，腾空后自动开始；' : '现在就能开始；') +
    '完成后这一行会自己更新。', 'success');
}
/* 队列单飞：算出这个任务前面还压着几个（在跑的 + 比我先排队的） */
function woAheadOf(t) {
  return woAllTasks().filter(function (x) {
    return x.id !== t.id && (x.status === 'running' || (x.status === 'pending' && x.seq < t.seq));
  }).length;
}
function woTaskCancel(t) {
  if (!t || (t.status !== 'running' && t.status !== 'pending')) return;
  if (t.auditId) {
    const r = state.rules.filter(function (x) { return x.id === t.auditId; })[0];
    if (r) r.audit = 'pending';
    t.status = 'canceled';
    if (state.route === '#/overview') renderView();
    toast('已取消本轮审核', r.name + ' ' + r.id + ' 退回「待 AI 审」：这一轮的结果不会落库，也不会自动重跑，要再审去规则页点重新审核。', 'warn');
    return;
  }
  const was = t.status;
  t.status = 'canceled';
  t.error = '你在 ' + WO_AT + ' 手动取消';
  if (state.route === '#/overview') renderView();
  toast('已取消', was === 'running'
    ? '队列已腾出来。正在跑的那一轮没法强杀，但它已经失去本次发布资格，跑完也不会写入结果。'
    : '这条还在排队、一行都没跑，已从队列里拿掉。', 'warn');
}
function woTaskRetry(t) {
  if (!t || t.status !== 'failed') return;
  t.status = 'pending';
  t.error = null;
  t.result = null;
  t.pct = 0;
  t.from = WO_AT;
  t.label = '重试（总览 ' + WO_AT + '）';
  t.seq = ++woSeq;
  woEnsureTicker();
  renderView();
  toast('已重新入队', '复用任务编号 ' + t.id + '，上一次的错误与结果都已清空。' +
    (woAheadOf(t) ? '前面还有 ' + woAheadOf(t) + ' 个。' : '队列已腾空，这一条马上开始。'), 'success');
}

function woFeedAll() { return (state.woFeed || []).concat(WO_FEED_SEED); }
function woFeedHidden(e) {
  if (!e.dup) return false;
  return woAllTasks().some(function (t) { return t.kind === e.dup && t.status !== 'done'; });
}
function woEntry(e, nav, iconName) {
  const done = e.done === 'yes';
  const row = '<div class="wo-entry' + (done ? ' is-done' : '') + '"' + (nav ? ' data-nav="' + nav + '"' : '') + '>' +
    '<span class="hold-dot ' + (done ? 'ok' : e.tone === 'red' ? 'err' : e.tone === 'gold' ? 'warn' : 'info') + '"></span>' +
    icon(iconName || 'chevron') +
    '<div class="wo-e-main"><div class="wo-e-name">' + esc(e.name) + '</div>' +
    (e.desc ? '<div class="wo-e-desc">' + esc(e.desc) + '</div>' : '') +
    '</div>' +
    '<span class="wo-e-go">' + esc(e.act || '查看') + ' ' + icon('arrow', 'sm') + '</span>' +
  '</div>';
  const side = e.key && e.gid ? '<button class="btn link xs" data-action="' + (done ? 'wo-undo-item' : 'wo-done-item') +
    '" data-group="' + e.gid + '" data-item="' + e.id + '">' + (done ? '撤下标记' : '今天先放过') + '</button>' : '';
  return side ? '<div class="wov-item">' + row + side + '</div>' : row;
}

/* ---------- 工作台总览：聚合与渲染 ---------- */
function woPlansToday() {
  return PLANS.filter(function (p) { return p.plan_date === WO_TODAY; });
}
function woPlanOfToday(code) {
  const list = woPlansToday().filter(function (p) { return p.stock_code === code; });
  return list.length ? list[0] : null;
}
function woGroupPending(g) {
  return g.items.filter(function (i) { return i.done !== 'yes'; }).length;
}

/* 待办分组：每条都直接等于「去那个页面做那个动作」，数字全部现算自各模块 */
function woTodoGroups() {
  const gs = [];

  const todo = hdTodo();
  const items = todo.map(function (r) {
    const v = hdVerdict(r);
    return {
      id: 'hd-' + r.id, icon: v === 'exit' ? 'bell' : 'shield',
      name: r.name + ' ' + r.code, desc: woHoldNote(r, v), act: '去处理',
      nav: '#/holdings?id=' + r.id, tone: v === 'exit' ? 'red' : 'gold',
      key: { code: 'holdings', field: 'label', label: '已记录处置' }
    };
  });
  const over = hdSentinelItems().filter(function (s) { return s.id === 'PS-TOTAL'; })[0];
  if (over) {
    items.push({ id: 'hd-account', icon: 'alert', name: over.title, desc: over.body,
      act: '看减仓建议', nav: '#/holdings?view=all', tone: 'red',
      key: { code: 'holdings', field: 'label', label: '已按建议减仓' } });
  }
  const noQuote = hdData().filter(function (r) { return hdVerdict(r) === 'info'; }).length;
  gs.push({ id: 'holdings', icon: 'shield', title: '持仓要处理', tone: 'red',
    sub: noQuote ? '另有 ' + noQuote + ' 只没有行情，算不出红线（要补一下价）' : '',
    items: items, nav: '#/holdings?view=todo', navLabel: '要我处理' });

  const buyable = CANDIDATE_POOL.filter(function (c) { return c.label === '可建仓'; });
  gs.push({ id: 'candidates', icon: 'star', title: '可建仓还没安排', tone: 'blue',
    sub: buyable.length ? '已出计划的会显示计划编号，点进去就是那份方案' : '',
    items: buyable.map(function (c) {
      const p = woPlanOfToday(c.stock_code);
      return { id: 'cand-' + c.stock_code, icon: 'plan', name: c.stock_name + ' ' + c.stock_code,
        desc: c.score + ' 分 · ' + c.tier + ' 级 · 建仓区间 ' + c.price_zone + '：' + c.conclusion,
        act: p ? '看今日计划' : '生建仓方案',
        nav: p ? '#/plans?id=' + p.id : '#/plans?gen=' + c.stock_code,
        key: { code: 'plans', field: 'status', label: '已出计划' } };
    }), nav: '#/candidates?mode=today', navLabel: '去候选池' });

  const pend = PLANS.filter(function (p) { return p.status === 'proposed'; });
  const todays = pend.filter(function (p) { return p.plan_date === WO_TODAY; });
  gs.push({ id: 'plans', icon: 'plan', title: '建仓计划等你确认', tone: 'gold',
    sub: pend.length > todays.length ? '另有 ' + (pend.length - todays.length) + ' 份更早的计划也还没确认' : '',
    items: pend.map(function (p) {
      const q = plQ(p);
      const e = plExecutable(q);
      return { id: 'plan-' + p.id, icon: e.ok ? 'plan' : 'alert',
        name: p.stock_name + ' ' + p.stock_code + ' · ' + p.plan_date,
        desc: e.ok ? '目标占比 ' + q.position_cap_pct + '%，分 ' + q.batches.length + ' 档共 ' +
          q.total_shares + ' 股 / ' + plMoney(q.total_amount) + ' 元'
          : '算出 ' + q.total_shares + ' 股：' + e.why + '（总资产口径按 ' + plMoney(q.total_capital) + ' 元算）',
        act: '去确认', nav: '#/plans?id=' + p.id, tone: e.ok ? '' : 'red',
        key: { code: 'plans', field: 'status', label: '已确认' } };
    }), nav: '#/plans?status=待确认', navLabel: '看待确认' });

  const rvPend = REVIEW_ROWS.filter(function (r) { return r.status === 'pending'; });
  gs.push({ id: 'reviews', icon: 'review', title: '复盘等你裁决', tone: 'blue',
    sub: SUG_ROWS.filter(function (s) { return s.status === 'pending'; }).length +
      ' 条闭环建议等处理（复盘产出，采纳后才进规则或经验）',
    items: rvPend.map(function (r) {
      return { id: 'rv-' + r.id, icon: 'review', name: r.name + ' ' + r.code + ' · 复盘 #' + r.id,
        desc: '这笔 ' + (r.pnl >= 0 ? '+' : '') + r.pnl.toFixed(1) + '%，AI 判「' + r.verdict +
          '」，要你确认是否按计划做的', act: '去裁决', nav: '#/reviews?id=' + r.id,
        key: { code: 'reviews', field: 'status', label: '已裁决' } };
    }), nav: '#/reviews?board=list', navLabel: '去交易复盘' });

  const expPend = EXPERIENCE_ROWS.filter(function (e) { return e.status === 'pending_review'; });
  gs.push({ id: 'experience', icon: 'layers', title: '经验等你审核', tone: 'blue',
    sub: expPend.length ? '审核通过后才会注入对应 Agent，不通过就退回' : '',
    items: expPend.map(function (e) {
      return { id: 'exp-' + e.id, icon: 'layers', name: e.title,
        desc: e.stage + '环节 · ' + (e.impact === 'high' ? '高影响' : '一般影响') + ' · 从已结算的复盘里归纳出来',
        act: '去审核', nav: '#/experience?id=' + e.id,
        key: { code: 'experience', field: 'status', label: '已审核' } };
    }), nav: '#/experience', navLabel: '去经验库' });

  const rulePend = state.rules.filter(function (r) { return ruleBucketOf(r) === 'todo'; });
  const govItems = rulePend.map(function (r) {
    return { id: 'rule-' + r.id, icon: 'shield', name: r.name + ' · ' + r.id,
      desc: (r.current === r.suggested ? '' : r.current + ' → ' + r.suggested + '：') +
        (r.audit === 'pass' ? 'AI 审核通过，采纳后才会写进规则表。风险：' : 'AI 审核未通过：') + (r.risk || ''),
      act: '去拍板', nav: '#/system/rules?bucket=todo&id=' + r.id,
      tone: r.audit === 'fail' ? 'red' : '', key: { code: 'rules', field: 'status', label: '已拍板' } };
  }).concat(state.factors.map(function (f) {
    return { id: 'factor-' + f.fid, icon: 'chart', name: f.name + ' · ' + f.fid,
      desc: f.months + '：' + f.reason, act: '去决策', nav: '#/system/factors',
      key: { code: 'factors', field: 'status', label: '已决策' } };
  }));
  gs.push({ id: 'governance', icon: 'check', title: '规则与因子等你拍板', tone: 'gold',
    sub: (function () {
      const aud = state.rules.filter(function (r) { return ruleBucketOf(r) === 'auditing'; }).length;
      return aud ? aud + ' 条正在 AI 审核（下面队列里能看到进度）' : '暂时没有建议在 AI 审核';
    })(),
    items: govItems, nav: '#/system/rules?bucket=todo', navLabel: '进规则审计' });

  gs.forEach(function (g) {
    const shown = state.woDone[g.id] || {};
    g.items.forEach(function (i) { i.gid = g.id; if (shown[i.id]) i.done = 'yes'; });
    g.pending = woGroupPending(g);
  });
  return gs.filter(function (g) { return g.items.length > 0; });
}

function woIndexRow() {
  const rg = miRegime(miIdx(WO_TODAY));
  const share = hdTotalShare();
  const items = [{ name: '上证指数', value: state.hdAccount.index, pct: 0.44 }]
    .concat(WO_INDEX_REST);
  return '<div class="wo-market">' +
    items.map(function (i) {
      return '<div class="wo-idx"><span class="wo-idx-name">' + esc(i.name) + '</span>' +
        '<span class="wo-idx-val">' + Number(i.value).toFixed(2) + '</span>' +
        '<span class="wo-idx-pct ' + (i.pct >= 0 ? 'wo-up' : 'wo-down') + '">' +
        (i.pct >= 0 ? '+' : '') + i.pct.toFixed(2) + '%</span></div>';
    }).join('') +
    '<span class="wo-sep"></span>' +
    '<span class="wo-band">' + esc((MI_REGIME_LABEL[rg.current_regime] || '结构未判定') + ' · ' +
      (MI_STAGE_LABEL[rg.regime_stage] || '')) + '</span>' +
    '<span class="wo-dim">两市成交 ' + esc(WO_MARKET_AMOUNT) + ' 万亿</span>' +
    '<span class="wo-sep"></span>' +
    '<span class="wo-dim">持仓 ' + esc(hdData().length) + ' 只 · 仓位 ' + share.toFixed(1) +
      '% / 上限 ' + HD_CAP.total + '%</span>' +
    '</div>';
}

function woConclusion() {
  const gs = woTodoGroups();
  const n = function (id) { const g = gs.filter(function (x) { return x.id === id; })[0]; return g ? g.pending : 0; };
  const redline = hdTodo().filter(function (r) { return hdVerdict(r) === 'exit'; }).length;
  const share = hdTotalShare();
  const deadPlans = woPlansToday().filter(function (p) { return !plExecutable(plQ(p)).ok; }).length;
  const rg = miRegime(miIdx(WO_TODAY));
  const jobs = WO_JOBS.filter(function (j) { return j.status === 'soon'; }).length;
  const failed = WO_JOBS.filter(function (j) { return j.status === 'failed'; }).length;
  const line = function (iconName, text, nav, act) {
    return '<div class="wov-line"' + (nav ? ' data-nav="' + nav + '"' : ' data-action="' + act + '"') + '>' +
      '<span class="wov-line-ico">' + icon(iconName, 'sm') + '</span><span>' + text + '</span>' +
      '<span class="wo-e-go">' + icon('arrow', 'sm') + '</span></div>';
  };
  return '<div class="card wov-concl">' +
    '<div class="card-title"><h3>今天要看的事</h3>' +
      '<button class="btn link sm" data-action="wo-scroll-todo">下面逐条列好了 ' + icon('arrow', 'sm') + '</button></div>' +
    line('shield', '<b>持仓：</b>' + n('holdings') + ' 只要处理，其中 ' + redline +
      ' 只已跌破止损永久红线（判定用的是 14:57 那轮，之后连续 6 轮失败）', '#/holdings?view=todo') +
    line('alert', '<b>账户：</b>股票占总资产 ' + share.toFixed(1) + '%，高于设定上限 ' + HD_CAP.total +
      '%；沪指 ' + state.hdAccount.index.toFixed(0) + ' 低于 ' + HD_CAP.indexBar +
      '，按现有规则建议压到 ' + HD_CAP.softCap + '% 以内', '#/holdings?view=all') +
    line('plan', '<b>机会：</b>今天可建仓 ' + CANDIDATE_POOL.filter(function (c) { return c.label === '可建仓'; }).length +
      ' 只，其中 ' + deadPlans + ' 份自动生成的建仓计划算出 0 股，需要你确认或改基准', '#/plans?status=待确认') +
    line('check', '<b>等你点头：</b>规则与因子 ' + n('governance') + ' 件 · 复盘 ' + n('reviews') +
      ' 笔 · 经验 ' + n('experience') + ' 条 · 计划 ' + n('plans') + ' 份', null, 'wo-scroll-todo') +
    '<div class="wov-ctx"><span>' + Number(WO_TODAY.slice(5, 7)) + ' 月 ' + Number(WO_TODAY.slice(8, 10)) +
      ' 日 ' + woWeekdayCN(WO_TODAY) + ' · 已收盘 · 页面时间 ' + WO_AT + ' · 定时任务 ' + WO_JOBS.length + ' 项' +
      (failed ? '，' + failed + ' 项失败' : '') + (jobs ? '，' + jobs + ' 项还没到点' : '') +
      ' · 结构：' + esc(MI_REGIME_LABEL[rg.current_regime] || '未判定') + '</span>' +
      '<button class="btn link sm" data-action="wo-reveal-schedule">今天的数据到齐了吗 ' + icon('arrow', 'sm') + '</button></div>' +
    '<div class="cap-note">' + icon('info') + '<div>所有数字都取自各页面自己的实时数据，本页只读：' +
      '不替任何标的做决定，也不下单、不接你的券商账户。</div></div>' +
  '</div>';
}

function woJobRow(j, i) {
  const dot = j.status === 'failed' ? 'err' : j.status === 'skip' ? 'warn' : j.status === 'soon' ? 'off' : 'ok';
  const label = j.status === 'failed' ? '失败' : j.status === 'skip' ? '本轮跳过'
    : j.status === 'soon' ? '还没到点' : j.status === 'done' && j.out ? esc(j.out) : '已执行';
  return '<div class="wov-job">' +
    '<span class="hold-dot ' + dot + '"></span>' +
    '<span class="wov-job-when mono">' + esc(j.at) + '</span>' +
    '<div class="wov-job-main"><div class="wov-job-name">' + esc(j.name) +
      (j.status !== 'done' ? ' ' + tag(j.status === 'failed' ? '执行失败' : j.status === 'skip' ? '跳过' : '未执行',
        j.status === 'failed' ? 'red' : 'mute') : '') + '</div>' +
      '<div class="wov-job-txt">' + label +
        (j.run && j.run !== j.at ? ' <span class="dim">· 实际 ' + esc(j.run) + '</span>' : '') + '</div>' +
      (j.reason ? '<div class="wov-job-txt dim">' + esc(j.reason) + '</div>' : '') +
      (j.effect ? '<div class="wov-job-impact">' + icon('alert', 'sm') + '<span>' + esc(j.effect) + '</span></div>' : '') +
    '</div>' +
    '<div class="wov-job-act">' +
      (j.manual === 'queue' ? '<button class="btn ghost sm" data-action="wo-act" data-job-rerun="' + j.id + '">' + icon('rotate', 'sm') + '补跑</button>' : '') +
      (j.manual === 'page' && j.nav ? '<button class="btn link sm" data-nav="' + j.nav + '">去那一页重跑 ' + icon('arrow', 'sm') + '</button>' : '') +
      (j.manual === 'derive' && j.nav ? '<button class="btn link sm" data-nav="' + j.nav + '">打开页面即重算 ' + icon('arrow', 'sm') + '</button>' : '') +
      (j.manual === 'none' ? '<span class="wov-job-none">没有手动入口</span>' : '') +
    '</div>' +
  '</div>';
}

function woTaskRow(t) {
  const bar = '<div class="wov-prog"><i id="wo-bar-' + t.id + '" style="width:' + (t.pct || 0) + '%"></i></div>';
  return '<div class="wov-task">' +
    '<div class="row"><b>' + esc(t.name) + '</b><span class="mono dim">' + esc(t.id) + '</span>' +
      '<span class="spacer"></span>' + woTaskTag(t.status) + '</div>' +
    '<div class="small muted">' + esc(t.label) + (t.from ? ' · 提交 ' + esc(t.from) : '') +
      (t.to ? ' · 结束 ' + esc(t.to) : '') + '</div>' +
    (t.status === 'running' ? bar : '') +
    (t.status === 'running' ? '<div class="small dim"><span id="wo-pct-' + t.id + '">' + (t.pct || 0) +
      '%</span> · 队列一次只跑一个任务，完成后这一行自己更新</div>' : '') +
    (t.status === 'pending' ? '<div class="small dim">' + (woAheadOf(t)
      ? '前面还有 ' + woAheadOf(t) + ' 个：队列一次只跑一个，排队是常态（不是卡死）'
      : '队列已腾空，这一条马上开始') + '</div>' : '') +
    (t.error ? '<div class="wov-job-impact">' + icon('alert', 'sm') + '<span>' + esc(t.error) + '</span></div>' : '') +
    (t.result ? '<div class="wov-job-impact">' + icon('check', 'sm') + '<span>' + esc(t.result) + '</span></div>' : '') +
    '<div class="row" style="margin-top:4px">' +
      (t.nav ? '<button class="btn link xs" data-nav="' + t.nav + '">' + esc(t.navLabel || '看这条规则') + '</button>' : '') +
      (t.refNav ? '<button class="btn link xs" data-nav="' + t.refNav + '">' + esc(t.refLabel || '看结果') + '</button>' : '') +
      '<span class="spacer"></span>' +
      (t.status === 'failed' ? '<button class="btn ghost sm" data-action="wo-act" data-task-retry="' + t.id + '">' + icon('rotate', 'sm') + '重试</button>' : '') +
      (t.status === 'running' || t.status === 'pending'
        ? '<button class="btn ghost sm" data-action="wo-act" data-task-cancel="' + t.id + '">取消</button>' : '') +
    '</div>' +
  '</div>';
}

/* ③ 今天的数据到齐了吗：定时任务时刻表 + 后台任务队列（默认收起来，从顶部那句展开） */
function woDataCard() {
  const open = state.woReveal.schedule;
  const shown = open ? WO_JOBS
    : WO_JOBS.filter(function (j) { return j.status !== 'done'; });
  const tasks = woAllTasks();
  const live = tasks.filter(function (t) { return t.status === 'running' || t.status === 'pending'; });
  const rest = tasks.filter(function (t) { return t.status !== 'running' && t.status !== 'pending'; });
  const head = '<div class="card-title"><h3>今天的数据到齐了吗</h3>' +
    '<span class="spacer"></span>' +
    '<span class="hint">' + WO_JOBS.filter(function (j) { return j.status === 'done'; }).length + ' 已执行 · ' +
      WO_JOBS.filter(function (j) { return j.status === 'failed'; }).length + ' 失败 · ' +
      WO_JOBS.filter(function (j) { return j.status === 'skip'; }).length + ' 跳过 · ' +
      WO_JOBS.filter(function (j) { return j.status === 'soon'; }).length + ' 没到点</span>' +
    '<button class="btn link sm" data-action="wo-reveal-schedule">' +
      (open ? '收起，只看有问题的' : '展开全部 ' + WO_JOBS.length + ' 项') +
      ' ' + icon('arrow', 'sm') + '</button></div>';
  const queue = '<div class="wov-sub">正在跑 / 排队的任务（' + live.length + '）' +
      '<span class="dim"> · 完成与失败的可重试，排队与执行中的可取消</span></div>' +
    (live.length ? '<div class="wov-tasks">' + live.map(woTaskRow).join('') + '</div>'
      : '<div class="wo-empty">队列是空的：没有正在跑的任务，也不需要你守着页面。</div>') +
    (state.woReveal.tasks && rest.length ? '<div class="wov-sub">今天跑完的（' + rest.length + '）</div>' +
      '<div class="wov-tasks">' + rest.map(woTaskRow).join('') + '</div>' : '') +
    (rest.length ? '<button class="btn link sm" data-action="wo-reveal-tasks">' +
      (state.woReveal.tasks ? '收起今天跑完的' : '看今天跑完的 ' + rest.length + ' 条') + ' ' + icon('arrow', 'sm') +
      '</button>' : '') +
    '<div class="cap-note">' + icon('info') + '<div>' + esc(WO_TASK_RULES[0]) + '</div></div>';
  const full = open
    ? '<div class="wov-jobs">' + shown.map(woJobRow).join('') + '</div>' +
      '<div class="cap-note mute">' + icon('clock') + '<div>' + esc(WO_JOBS_NOTE) + ' 失败的任务不自动补数：' +
      '重跑只能拿当前口径重算，补不回当时那个时刻的行情；要按当时的价格复盘，去持仓页把成交价记进买卖明细。</div></div>' +
      '<div class="cap-note mute">' + icon('info') + '<div>队列硬规则：' +
      WO_TASK_RULES.slice(1).map(esc).join(' ') + '</div></div>'
    : '';
  return '<div class="card wov-data" id="wov-data">' + head + queue + full + '</div>';
}

function woGroupCard(g) {
  const reveal = state.woReveal['g:' + g.id];
  const head = '<div class="wo-head">' + icon(g.icon) + '<span class="wo-title">' + esc(g.title) + '</span>' +
    '<span class="wo-count">' + (g.pending ? g.pending + ' 件' : '今天没有') + '</span>' +
    '<span class="spacer"></span>' +
    '<button class="btn link sm" data-action="wo-done-group" data-group="' + g.id + '">' +
      (state.woDone[g.id] && Object.keys(state.woDone[g.id]).length ? '全部撤下标记' : '这组今天都处理完了') + '</button>' +
    '</div>';
  const list = reveal ? g.items : g.items.slice(0, 3);
  return '<div class="wo-card ' + g.tone + '">' + head +
    '<div class="wo-entries">' + (g.items.length
      ? list.map(function (i) { return woEntry(i, i.nav, i.icon); }).join('')
      : '<div class="wo-empty">这个筛选下没有了。</div>') + '</div>' +
    (g.items.length > list.length ? '<button class="btn link sm" data-action="wo-reveal-group" data-group="' +
      g.id + '">还有 ' + (g.items.length - list.length) + ' 件 ' + icon('arrow', 'sm') + '</button>' : '') +
    (g.sub ? '<div class="wov-gnote">' + esc(g.sub) + '</div>' : '') +
    '<div class="wo-foot"><button class="btn link sm" data-nav="' + g.nav + '">' + esc(g.navLabel) +
      ' ' + icon('arrow', 'sm') + '</button></div>' +
  '</div>';
}

function woTodoCard() {
  const gs = woTodoGroups();
  const groups = state.woOnlyTodo ? gs.filter(function (g) { return g.pending > 0; }) : gs;
  const total = gs.reduce(function (s, g) { return s + g.pending; }, 0);
  const doneAll = gs.reduce(function (s, g) { return s + (g.items.length - g.pending); }, 0);
  return '<div class="card" id="wov-todo">' +
    '<div class="card-title"><h3>要你处理</h3>' +
      '<span class="spacer"></span><span class="hint">' + total + ' 件在等 · ' + doneAll + ' 件你今天已在本页标记过</span>' +
      '<button class="btn link sm" data-action="wo-toggle-only">' + (state.woOnlyTodo ? '看全部分组' : '只看要我处理的') +
      ' ' + icon('arrow', 'sm') + '</button></div>' +
    '<div class="wo-actions">' + (groups.length
      ? groups.map(woGroupCard).join('')
      : '<div class="wo-empty">该你决定的都处理完了，剩下的是只读摘要。</div>') + '</div>' +
    '<div class="cap-note">' + icon('info') + '<div>「今天已标记」只是把这张牌收起来，方便看清剩下的；' +
      '真正的处置要回对应页面记录（成交、裁决、采纳），这里不写库。' +
      (doneAll ? ' <button class="btn link xs" data-action="wo-clear-done">撤下全部标记</button>' : '') + '</div></div>' +
  '</div>';
}

function woOutputNum(v, nav, unit, cls) {
  return '<div class="metric"><div class="metric-label">' + esc(unit) + '</div>' +
    '<div class="metric-value ' + (cls || '') + '">' + esc(String(v)) + '</div>' +
    (nav ? '<button class="btn link xs" data-nav="' + nav + '">怎么来的 ' + icon('arrow', 'sm') + '</button>'
      : '<div class="metric-sub">本页不重算</div>') + '</div>';
}

/* ⑤ 今天产出：每个数字都是对应页面此刻算出来的，点进去就是它的明细 */
function woOutputCard() {
  const acc = state.hdAccount;
  const mv = hdTotalMv();
  const pnl = hdTodayPnl();
  const paper = ppData().filter(function (a) { return a.id === state.ppAcc; })[0] || ppData()[0];
  const val = ppValuation(paper);
  return '<div class="card">' +
    '<div class="card-title"><h3>今天产出</h3><span class="hint">' + esc(WO_TODAY) + ' 收盘口径</span></div>' +
    '<div class="metric-strip">' +
      woOutputNum(CANDIDATE_POOL.length, '#/candidates?mode=today', '今日候选（只）') +
      woOutputNum(CANDIDATE_POOL.filter(function (c) { return c.label === '可建仓'; }).length,
        '#/candidates?mode=today', '其中可建仓（只）', 'ok') +
      woOutputNum(woPlansToday().length, '#/plans?date=' + WO_TODAY, '今日建仓计划（份）') +
      woOutputNum((pnl >= 0 ? '+' : '-') + Math.abs(Math.round(pnl)).toLocaleString('zh-CN'),
        '#/holdings?view=all', '今日浮动盈亏（元）', pnl >= 0 ? 'up' : 'down') +
      woOutputNum((val.pnlPct >= 0 ? '+' : '') + val.pnlPct.toFixed(2) + '%',
        '#/paper?acc=' + paper.id, paper.name + ' 累计', val.pnl >= 0 ? 'up' : 'down') +
    '</div>' +
    '<div class="cap-note">' + icon('info') + '<div>账户总资产 ' + plMoney(acc.total) + ' 元 = 股票市值 ' +
      plMoney(mv) + ' + 可用现金 ' + plMoney(hdCash()) + '（券商 App 截图录入后由持仓实时价现算）。' +
      '模拟盘是独立账本（模拟总资产 ' + plMoney(Math.round(val.equity)) + ' 元），与你的真实持仓无关；' +
      '本页只读你的持仓记录，绝不代你向券商下单。</div></div>' +
  '</div>';
}

/* ④ 今天动作与发现：标题在别处已经说过的会自动隐藏 */
function woFeedCard() {
  const list = woFeedAll().filter(function (e) { return !woFeedHidden(e); });
  const mine = list.filter(function (e) { return e.mine; });
  const rest = list.filter(function (e) { return !e.mine; });
  const row = function (e) {
    return '<div class="tl-item"' + (e.nav ? ' data-nav="' + e.nav + '"' : '') + '>' +
      '<span class="tl-dot ' + (e.who === 'you' ? 'ok' : e.who === 'ai' ? 'info' : '') + '"></span>' +
      '<div class="tl-head"><span class="tl-title">' + esc(e.title) + '</span>' +
        actorChip({ actor: e.who === 'you' ? 'human' : e.who }) +
        '<span class="tl-time">' + esc(e.t) + '</span></div>' +
      '<div class="tl-body">' + esc(e.body) + '</div></div>';
  };
  return '<div class="card">' +
    '<div class="card-title"><h3>今天动作与发现</h3><span class="spacer"></span>' +
      '<button class="btn link sm" data-nav="#/system/overview">全部留痕 ' + icon('arrow', 'sm') + '</button></div>' +
    (mine.length ? '<div class="wov-sub">你在这页做的（' + mine.length + '）</div>' +
      '<div class="timeline">' + mine.map(row).join('') + '</div>' : '') +
    (rest.length ? '<div class="timeline">' + rest.map(row).join('') + '</div>'
      : '<div class="wo-empty">今天没有额外的产出：能列的都列在上面的待办里了。</div>') +
  '</div>';
}

function renderWorkspaceOverview() {
  const gs = woTodoGroups();
  const total = gs.reduce(function (s, g) { return s + g.pending; }, 0);
  return '<div>' +
    '<div class="subhead">' +
      '<div><h2>今天这一屏</h2><p>' + esc(WO_TODAY) + ' ' + esc(woWeekdayCN(WO_TODAY)) +
        ' · 已收盘 · 页面时间 ' + WO_AT + ' · 上面是结论，往下每一行都能点进现场</p></div>' +
      '<div class="spacer"></div>' +
      '<button class="btn" data-action="task-center">' + icon('clock', 'sm') + '任务中心</button>' +
      '<button class="btn" data-action="refresh">' + icon('rotate', 'sm') + '刷新</button>' +
    '</div>' +
    woConclusion() +
    woIndexRow() +
    woTodoCard() +
    woDataCard() +
    '<div class="wo-split">' + woOutputCard() + woFeedCard() + '</div>' +
    (total > 0 ? '<div class="cap-note mute">还有 ' + total + ' 件事等你处理，都在上面那一卡里；' +
      '本页不替你决定，也不改变任何规则。</div>' : '') +
  '</div>';
}

/* 「周一」从日期算，不写死：模拟日期一旦改动，这里不会说谎 */
function woWeekdayCN(dateStr) {
  const cn = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  const p = String(dateStr).split('-');
  const d = new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
  return cn[d.getDay()] || '';
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
        '<div class="cap-note" style="margin-top:10px">' + icon('info') + '<div>这里只列与「' + esc(c.stock_name) + '」直接相关的消息；全市场盘面消息不在这里铺开，板块层面的判断看市场研判。</div></div>'
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
      '<span class="spacer"></span>' +
      '<button class="btn link sm" data-nav="#/market-intel">先看今天是不是主线行情 ' + icon('arrow', 'sm') + '</button>' +
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
  const n = 121;
  const bars = [];
  for (let i = -159; i < n; i++) {
    const t = (Math.max(0, i) / (n - 1)) * (base.length - 1);
    const k = Math.floor(t), f = t - k;
    const a = base[k], b = base[Math.min(k + 1, base.length - 1)];
    const close = i < 0 ? base[0] * (1 + i * 0.00015 + Math.sin(i * 0.07) * 0.03) : a + (b - a) * f;
    const wob = Math.sin(i * 2.7 + seed) * 0.009;
    const open = close * (1 + wob);
    const hi = Math.max(open, close) * (1 + 0.005 + Math.abs(wob) * 0.5);
    const lo = Math.min(open, close) * (1 - 0.005 - Math.abs(wob) * 0.5);
    bars.push({ open, close, high: hi, low: lo, vol: 0.35 + Math.abs(Math.sin(i * 1.31 + seed)) * 0.65 });
  }
  return bars;
}
function code5(code) { let s = 0; for (const ch of String(code)) s += ch.charCodeAt(0); return s % 7; }

function candKlineHtml(c, anchorLabel, compact) {
  const anch = anchorLabel || '选中日';
  const history = mockBars(c);
  const bars = history.slice(159);
  const averages = [5, 10, 40, 160].map((period) => ({ period,
    values: bars.map((_, i) => history.slice(i + 160 - period, i + 160).reduce((sum, b) => sum + b.close, 0) / period)
  }));
  const w = 640, ph = 208, vh = 40, padL = 44, padR = 10;
  const maValues = averages.flatMap((a) => a.values);
  const lo = Math.min(...bars.map((b) => b.low), ...maValues);
  const hi = Math.max(...bars.map((b) => b.high), ...maValues);
  const span = hi - lo || 1;
  const bw = (w - padL - padR) / bars.length;
  const y = (v) => 12 + (1 - (v - lo) / span) * (ph - 24);
  const anchorIdx = 60;
  const anchorX = padL + anchorIdx * bw + bw / 2;
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
      averages.map((a) => '<path class="wk-ma ma' + a.period + '" d="' + maPath(a.values) + '"><title>MA' + a.period + ' · ' + a.period + ' 日均线</title></path>').join('') +
      '<line class="wk-anchor-line" x1="' + anchorX + '" y1="8" x2="' + anchorX + '" y2="' + (ph + vh) + '"/>' +
      '<text class="wk-anchor-text" x="' + (anchorX + 4) + '" y="18">' + esc(anch) + '</text>' +
    '</svg>' +
    '<div class="wk-legend wk-averages">' + averages.map((a) => '<span class="ma' + a.period + '" title="' + a.period + ' 个交易日收盘价的简单平均"><i class="l ma' + a.period + '"></i>MA' + a.period + ' <b class="mono">' + a.values[a.values.length - 1].toFixed(2) + '</b></span>').join('') + '</div>' +
    '<div class="wk-legend"><span><i class="bull"></i>阳线（涨）</span><span><i class="bear"></i>阴线（跌）</span><span>下方为成交量 · 原型示意，非真实行情</span></div>' +
    (compact ? '' : '<div class="wk-links"><span class="hint">真实行情：</span>' +
      quoteUrls(c.stock_code).map((q) => '<a class="btn sm" href="' + q.url + '" target="_blank" rel="noopener noreferrer">' + esc(q.name) + ' ' + icon('external', 'sm') + '</a>').join('') + '</div>') +
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
/* ============================================================
   持仓监控（#/holdings）
   口径来自生产接口，正式页面全部走真接口，这里是示意数据：
     GET  /api/holdings/quotes              持仓 + 实时行情 + 参考风控位（约 60s 缓存）
     GET  /api/red_line_check               四条红线扫描（约 300s 缓存）
     GET  /api/holdings/{id}/trades         操作流水
     GET  /api/holdings/{id}/sell-decisions 卖出决策历史
     GET  /api/holdings/take-profit-plan    止盈与仓位计划
     POST /api/holdings/{id}/add|exit|cost  加仓 / 减仓清仓 / 修正成本（只记录人工成交，不下单）
     POST 后台任务 monitor_all / portfolio_sentinel / sell_decision
   ============================================================ */
const HD_CAP = { total: 60, gradeA: 30, c3: 0.92, drawdown: 30, indexBar: 4000, softCap: 20 };

const HD_ACCOUNT = { total: 486200, cash: 66115, quoteTime: '2026-11-16 14:56:12', index: 3962.18 };

/* 每只持仓：verdict 由红线自动推导，concls 只写可能到达的结论 */
const HD_ROWS = [
  {
    id: 2071, code: '603501', name: '韦尔股份', source: '真实交易', entry: '2026-10-21',
    shares: 1250, cost: 118.60, price: 126.30, today: 1.2, dd: -4.6,
    stop: 109.11, tp: 142.32, targetPct: 30, suggestPct: 20,
    trail: { stage: '第二档（+15%）未到', hit: false, next: '涨到 136.39 上移止盈' },
    plan: { id: 812, batch: '2026-10-20' }, alerts: 1,
    rules: [{ id: 'RC-1050', name: '单股最大仓位上限' }, { id: 'RC-1042', name: '移动止盈回撤阈值' }],
    concls: {
      reduce: '盈利不错，但单票已经占总资产 32.5%，超过 A 级 30% 上限。先减一档把集中度压回上限内，不等回调。',
      hold: '单票占比回到上限内，止损未破，继续拿。',
      exit: '跌破止损红线，全部离场，不再讨论基本面。'
    },
    scenes: [
      { k: 'up', c: '站上 136.39（+8.0%）', a: '移动止盈上移，按新止盈位持有；再涨到 142.32 减第二档 400 股' },
      { k: 'flat', c: '120.00 - 136.39 之间', a: '在 126 附近减 400 股，把单票占比压回 25% 以内，剩下的按 109.11 止损' },
      { k: 'dn', c: '跌破 109.11（成本 ×0.92）', a: '剩余全部离场，跌破红线不补仓、不摊薄' }
    ],
    decision: {
      action: 'partial', conf: 'high', ratio: 0.33, at: '2026-11-16 09:31',
      final: '先减三分之一把集中度压回上限内，不等回调；剩余仓位交给移动止盈。',
      dims: [
        { dim: '趋势', score: 74, verdict: '支持', advice: '日线仍在 20 日均线上方，未破位' },
        { dim: '量能', score: 58, verdict: '支持', advice: '今日缩量上涨，追高动能一般' },
        { dim: '板块', score: 66, verdict: '支持', advice: '半导体主线未切换，但资金开始分散' },
        { dim: '盈亏', score: 41, verdict: '风险', advice: '浮盈 +6.5%，未到第三档移动止盈' },
        { dim: '风险', score: 30, verdict: '风险', advice: '单票占比 32.5%，超过 A 级 30% 上限' }
      ],
      reasons: [
        '单票市值 157,875 元，占总资产 32.5%，触发 C1 集中度预警。',
        '现价高于买入区上沿，属于「已涨上来」的持仓，继续加仓的赔率变差。',
        '止损 109.11 未破，趋势维度没有要求清仓，因此是减仓而不是离场。'
      ],
      zone: '126.00 - 128.50 分两笔',
      risk: '半导体今日冲高回落，若明日低开可把执行价下移一档，但不要为了等价格而不减仓位。',
      checks: [
        { label: '未跌破 C3 止损线（109.11）', ok: true },
        { label: '单票占比未超 A 级上限（30%）', ok: false },
        { label: '总仓位未超防御期软上限（20%）', ok: false },
        { label: '当日未重复减仓', ok: true },
        { label: '无未执行的清仓红线告警', ok: true }
      ]
    },
    decisions: [
      { at: '2026-11-16 09:31', action: 'partial', conf: 'high', one: '减三分之一压集中度' },
      { at: '2026-11-12 09:35', action: 'hold', conf: 'medium', one: '趋势完好，继续持有' }
    ],
    trades: [
      { side: 'buy', shares: 450, price: 112.40, date: '2026-10-21', note: '首仓，候选池 10-20 批次评分 88' },
      { side: 'buy', shares: 800, price: 122.10, date: '2026-11-04', note: '突破回踩加仓' },
      { side: 'sys', shares: 0, price: 0, date: '2026-11-04', note: '加仓后成本重算 118.60，止损上移至 109.11' }
    ],
    records: [
      { date: '2026-10-21', price: 112.40, shares: 450, created: '2026-10-21 09:41', status: '历史买入' },
      { date: '2026-11-04', price: 122.10, shares: 800, created: '2026-11-04 10:02', status: '当前有效' }
    ]
  },
  {
    id: 2064, code: '600519', name: '贵州茅台', source: '真实交易', entry: '2026-09-28',
    shares: 100, cost: 1520.00, price: 1392.00, today: -1.02, dd: -8.4,
    stop: 1398.40, tp: 1824.00, targetPct: 20, suggestPct: 0,
    trail: null, plan: { id: 774, batch: '2026-09-25' }, alerts: 3,
    rules: [{ name: 'C3 止损红线：成本 ×0.92，永久红线' }],
    concls: {
      exit: '现价 1392.00 已跌破止损红线 1398.40（成本 1520 × 0.92）。这是系统唯一不给你商量的动作：今天必须清仓。',
      hold: '未跌破止损，继续持有观察。'
    },
    scenes: [
      { k: 'up', c: '收复 1398.40 之上', a: '仍然按红线执行：反弹只影响卖出价，不改变「要离场」这个结论' },
      { k: 'flat', c: '1380 - 1400 之间', a: '在 1395 附近一次清仓 100 股，不留「再看看」' },
      { k: 'dn', c: '继续跌破 1380', a: '直接市价清仓，跌破红线后每多等一天都是额外风险' }
    ],
    decision: {
      action: 'exit', conf: 'high', ratio: null, at: '2026-11-16 09:30',
      final: '跌破止损红线，全部清仓。这笔的亏损是规则成本，不是判断错误。',
      dims: [
        { dim: '趋势', score: 22, verdict: '风险', advice: '跌破 20 日与 60 日均线，日线破位' },
        { dim: '量能', score: 35, verdict: '风险', advice: '下跌放量，承接不足' },
        { dim: '板块', score: 40, verdict: '风险', advice: '白酒板块资金持续净流出' },
        { dim: '盈亏', score: 12, verdict: '风险', advice: '浮亏 -8.4%，已过止损位' },
        { dim: '风险', score: 18, verdict: '风险', advice: '防御期单票 28.6% 占比偏高' }
      ],
      reasons: [
        '现价 1392.00 低于 C3 止损位 1398.40，触发永久红线。',
        '五个维度全部偏风险，没有任何一个维度支持继续持有。',
        '防御期（沪指 3962 < 4000）本就该降仓位，两个理由方向一致。'
      ],
      zone: '1385 - 1400 一次出清',
      risk: '白酒若明日跳空低开会有滑点；不要为了等一个价而挂单不成交。',
      checks: [
        { label: '未跌破 C3 止损线（1398.40）', ok: false },
        { label: '无更高优先级的停牌/涨跌停限制', ok: true },
        { label: '清仓股数等于持仓股数', ok: true },
        { label: '离场后会自动生成复盘', ok: true }
      ]
    },
    decisions: [
      { at: '2026-11-16 09:30', action: 'exit', conf: 'high', one: '跌破止损，清仓' },
      { at: '2026-11-17 09:32', action: 'reduce', conf: 'medium', one: '减半仓，接近止损' },
      { at: '2026-11-10 09:30', action: 'hold', conf: 'medium', one: '未到止损' }
    ],
    trades: [
      { side: 'buy', shares: 100, price: 1520.00, date: '2026-09-28', note: '建仓计划 #774' },
      { side: 'sys', shares: 0, price: 0, date: '2026-11-16', note: '监控扫描：跌破 C3 止损，生成红线告警' }
    ],
    records: [
      { date: '2026-09-28', price: 1520.00, shares: 100, created: '2026-09-28 10:15', status: '当前有效' }
    ]
  },
  {
    id: 2075, code: '300750', name: '宁德时代', source: '真实交易', entry: '2026-10-30',
    shares: 200, cost: 214.50, price: 268.40, today: 1.35, dd: -5.2,
    stop: 245.00, tp: 285.60, targetPct: 15, suggestPct: 10,
    trail: { stage: '第三档（+25%）已触发', hit: true, next: '止盈位已上移至 245.00' },
    plan: { id: 803, batch: '2026-10-29' }, alerts: 1,
    rules: [{ id: 'RC-1042', name: '移动止盈回撤阈值' }],
    concls: {
      reduce: '浮盈 +25.1% 已到 K139 第三档，规则要求减 1/4 落袋；移动止盈位已上移到 245.00。',
      hold: '未到下一档，按移动止盈位持有。'
    },
    scenes: [
      { k: 'up', c: '涨到 285.60（+6.4%）', a: '减第二笔 50 股，止盈位再上移一档' },
      { k: 'flat', c: '245.00 - 285.60 之间', a: '先按第三档减 50 股，剩下的拿到止盈位被跌破为止' },
      { k: 'dn', c: '跌破 245.00（上移后的止盈位）', a: '剩余全部离场，这一笔已经赚到了，不要把利润坐回去' }
    ],
    decision: {
      action: 'partial', conf: 'high', ratio: 0.25, at: '2026-11-16 09:32',
      final: '到档就减，不要因为「还在涨」跳过这一档。',
      dims: [
        { dim: '趋势', score: 78, verdict: '支持', advice: '沿 10 日均线上行，趋势最强的一只' },
        { dim: '量能', score: 69, verdict: '支持', advice: '放量新高，量能未背离' },
        { dim: '板块', score: 62, verdict: '支持', advice: '锂电中游补库，板块资金回流' },
        { dim: '盈亏', score: 88, verdict: '风险', advice: '浮盈 +25.1%，已到第三档减仓线' },
        { dim: '风险', score: 71, verdict: '支持', advice: '单票占比 11.0%，在上限内' }
      ],
      reasons: [
        '浮盈 +25.1% 触发 K139 第三档，规则要求减仓 1/4。',
        '趋势与量能仍支持，因此只减一档，不清仓。',
        '移动止盈位上移至 245.00，跌破即全部离场。'
      ],
      zone: '266.00 - 270.00 减 50 股',
      risk: '若减完后继续拉升，剩余仓位仍能吃到主升，不要为了多赚而不减。',
      checks: [
        { label: '未到 C3 止损线（245.00）', ok: true },
        { label: '已到 K139 减仓档', ok: true },
        { label: '单票占比未超上限（11.0% / 30%）', ok: true },
        { label: '当日未重复减仓', ok: true }
      ]
    },
    decisions: [
      { at: '2026-11-16 09:32', action: 'partial', conf: 'high', one: '第三档到，减 1/4' },
      { at: '2026-11-06 09:31', action: 'partial', conf: 'medium', one: '第二档到，减 100 股（已执行）' }
    ],
    trades: [
      { side: 'buy', shares: 300, price: 214.50, date: '2026-10-30', note: '建仓计划 #803' },
      { side: 'sell', shares: 100, price: 241.00, date: '2026-11-06', note: 'K139 第二档减仓' },
      { side: 'sys', shares: 0, price: 0, date: '2026-11-16', note: '止盈位上移至 245.00，第三档触发' }
    ],
    records: [
      { date: '2026-10-30', price: 214.50, shares: 300, created: '2026-10-30 09:52', status: '历史买入' },
      { date: '2026-11-06', price: 241.00, shares: -100, created: '2026-11-06 14:20', status: '当前有效' }
    ]
  },
  {
    id: 2078, code: '002415', name: '海康威视', source: '真实交易', entry: '2026-11-11',
    shares: 1000, cost: 32.00, price: 31.26, today: -2.3, dd: -6.1,
    stop: 29.44, tp: 38.40, targetPct: 10, suggestPct: 10,
    trail: null, plan: { id: 821, batch: '2026-11-10' }, alerts: 1,
    rules: [{ name: 'C3 止损红线：成本 ×0.92，永久红线' }],
    concls: {
      watch: '今天放量跌 2.3%，距止损只剩 6.2%。这一只不用现在动手，但要知道「跌破 29.44 就走」。',
      exit: '跌破止损红线，按规则清仓。',
      hold: '量能收敛，未破位，继续持有。'
    },
    scenes: [
      { k: 'up', c: '收复 32.00 成本线', a: '回到成本之上，撤销「到价提醒」，继续按 29.44 止损' },
      { k: 'flat', c: '30.50 - 32.00 之间', a: '不动，也不加仓——防御期不摊薄亏损仓位' },
      { k: 'dn', c: '跌破 29.44（成本 ×0.92）', a: '全部清仓 1000 股，系统会同时把这笔送进复盘' }
    ],
    decision: {
      action: 'hold', conf: 'medium', ratio: null, at: '2026-11-16 09:33',
      final: '还没到止损，不提前砍；但今天已经放量下跌，跌破 29.44 不要再等确认。',
      dims: [
        { dim: '趋势', score: 44, verdict: '风险', advice: '跌破 20 日均线，尚未破 60 日' },
        { dim: '量能', score: 38, verdict: '风险', advice: '下跌放量，抛压未收敛' },
        { dim: '板块', score: 52, verdict: '中性', advice: '安防/AI 视觉无明确主线催化' },
        { dim: '盈亏', score: 61, verdict: '支持', advice: '浮亏 -2.3%，距止损还有 6.2%' },
        { dim: '风险', score: 74, verdict: '支持', advice: '单票占比 6.4%，可承受' }
      ],
      reasons: [
        '未触发 C3 止损，也没有到减仓档，规则层面不要求动手。',
        '量能与趋势偏风险，因此把这笔标成「到价了要盯」，而不是正常持有。'
      ],
      zone: '不设卖出价；跌破 29.44 直接执行',
      risk: '如果明日继续放量下杀，可能一步跌破止损，届时按开盘价执行不要挂单等反弹。',
      checks: [
        { label: '未到 C3 止损线（29.44）', ok: true },
        { label: '单票占比未超上限', ok: true },
        { label: '无未了结红线告警', ok: false }
      ]
    },
    decisions: [{ at: '2026-11-16 09:33', action: 'hold', conf: 'medium', one: '未到止损，盯 29.44' }],
    trades: [
      { side: 'buy', shares: 1000, price: 32.00, date: '2026-11-11', note: '建仓计划 #821，第二档买入' }
    ],
    records: [
      { date: '2026-11-11', price: 32.00, shares: 1000, created: '2026-11-11 13:06', status: '当前有效' }
    ]
  },
  {
    id: 2069, code: '601012', name: '隆基绿能', source: '真实交易', entry: '2026-10-14',
    shares: 900, cost: 24.80, price: 27.10, today: 0.6, dd: -3.4,
    stop: 22.82, tp: 28.52, targetPct: 10, suggestPct: 8,
    trail: { stage: '第一档（+15%）未到', hit: false, next: '涨到 28.52 上移止盈' },
    plan: { id: 791, batch: '2026-10-13' }, alerts: 0,
    rules: [{ id: 'RC-1042', name: '移动止盈回撤阈值' }],
    concls: {
      hold: '浮盈 +9.3%，距第一档止盈还有 5.2%，趋势没坏。这一只今天什么都不用做。'
    },
    scenes: [
      { k: 'up', c: '涨到 28.52（+5.2%）', a: '止盈上移并减 300 股，锁定第一档利润' },
      { k: 'flat', c: '25.50 - 28.52 之间', a: '不动' },
      { k: 'dn', c: '跌破 24.80 成本线', a: '减仓一半，不等到止损；跌破 22.82 全部离场' }
    ],
    decision: null,
    decisions: [{ at: '2026-11-13 09:34', action: 'hold', conf: 'medium', one: '未到档，继续持有' }],
    trades: [
      { side: 'buy', shares: 900, price: 24.80, date: '2026-10-14', note: '建仓计划 #791' }
    ],
    records: [
      { date: '2026-10-14', price: 24.80, shares: 900, created: '2026-10-14 10:11', status: '当前有效' }
    ]
  },
  {
    id: 2081, code: '002138', name: '顺络电子', source: '真实交易', entry: '2026-11-18',
    shares: 400, cost: 34.20, price: null, today: null, dd: null,
    stop: 31.46, tp: 41.04, targetPct: 5, suggestPct: 5,
    trail: null, plan: null, alerts: 0, rules: [],
    concls: {
      info: '今天没取到行情（可能是新股/停牌/盘后延迟），所以不给你结论。先核对成本与股数，行情回来后自动补判断。'
    },
    scenes: null,
    decision: null, decisions: [],
    trades: [
      { side: 'buy', shares: 200, price: 34.20, date: '2026-11-18', note: '人工录入' },
      { side: 'buy', shares: 200, price: 34.20, date: '2026-11-18', note: '同一天重复录入，已被自动忽略' }
    ],
    records: [
      { date: '2026-11-18', price: 34.20, shares: 200, created: '2026-11-18 14:31', status: '重复录入（已自动忽略）' },
      { date: '2026-11-18', price: 34.20, shares: 200, created: '2026-11-18 14:33', status: '当前有效' }
    ]
  }
];

const HD_EXITED = [
  { code: '600893', name: '航发动力', entry: '2026-10-09', exit: '2026-11-06', shares: 600, cost: 42.30, out: 46.10, pnl: 9.0, note: '止盈第二档全部离场', reviewId: 1039 },
  { code: '601869', name: '长飞光纤', entry: '2026-09-22', exit: '2026-10-30', shares: 300, cost: 31.80, out: 29.10, pnl: -8.5, note: '跌破止损清仓', reviewId: 1031 }
];

/* 组合级风控：全部由持仓实时算出来，记录一笔之后这里会跟着变 */
function hdSentinelItems() {
  const out = [];
  const share = hdTotalShare();
  const defensive = state.hdAccount.index < HD_CAP.indexBar;
  const breached = hdData().map((r) => ({ r: r, red: hdReds(r) })).filter((x) => x.red[2].st === 'bad');
  const over = hdData().map((r) => ({ r: r, red: hdReds(r) })).filter((x) => x.red[0].st === 'bad' || x.red[0].st === 'todo');
  if (breached.length) {
    out.push({ id: 'PS-BREACH', level: 'bad', at: '2026-11-16 09:31', nav: '#/holdings?id=' + breached[0].r.id, navLabel: '查看止损详情',
      title: '优先关注止损：' + breached.map((x) => x.r.name + '已跌破设定的止损价').join('；'),
      body: '按当前止损规则，这类持仓需要优先处理。请到详情核对价位与处理要求；实际成交后记下买卖结果，账户仓位会随之更新。' });
  }
  if (share > HD_CAP.total || (defensive && share > HD_CAP.softCap)) {
    out.push({ id: 'PS-TOTAL', level: share > HD_CAP.total ? 'bad' : 'todo', at: '2026-11-16 15:02', nav: '#/alerts', navLabel: '查看仓位提醒',
      title: '账户仓位偏高：股票占总资产 ' + share.toFixed(1) + '%，高于' + (share > HD_CAP.total ? '设定上限 ' + HD_CAP.total + '%' : '当前建议上限 ' + HD_CAP.softCap + '%'),
      body: '总资产 ' + hdMoney(state.hdAccount.total) + ' 元，其中股票市值 ' + hdMoney(hdTotalMv()) + ' 元，可用现金 ' + hdMoney(hdCash()) + ' 元。仓位越高，账户越容易受到股价波动影响。' +
        (defensive ? '当前沪指 ' + state.hdAccount.index.toFixed(0) + '，低于设定的 ' + HD_CAP.indexBar + ' 点；按现有规则，建议将总仓位控制在 ' + HD_CAP.softCap + '% 以内。' : '可结合上面的持仓详情，核对哪些需要减仓。') });
  }
  if (over.length) {
    out.push({ id: 'PS-C1', level: 'todo', at: '2026-11-16 15:02', nav: '#/holdings?id=' + over[0].r.id, navLabel: '查看持仓占比',
      title: '留意持仓集中：' + over.map((x) => x.r.name + '占总资产 ' + hdShare(x.r).toFixed(1) + '%').join('；') + '，高于单只股票上限 ' + HD_CAP.gradeA + '%',
      body: '单只股票占比过高时，它的涨跌会更明显地影响整个账户。查看这只股票的减仓建议，记录成交后再检查占比是否回到上限内。' });
  }
  if (!out.length) {
    out.push({ id: 'PS-OK', level: 'done', at: '2026-11-16 15:02', nav: '#/alerts', navLabel: '查看过往提醒',
      title: '暂未发现超限提醒', body: '按当前已录入的数据和可用行情，总仓位 ' + share.toFixed(1) + '%，未发现止损或持仓占比超限。可继续按原计划关注；没有提醒不代表没有投资风险。' });
  }
  return out;
}

/* ---------- 计算 ---------- */
function hdData() {
  if (!state.holdings) {
    state.holdings = clone(HD_ROWS);
    state.exited = clone(HD_EXITED).map((x, i) => Object.assign(x, { id: -i - 1 }));
    state.hdAccount = Object.assign({}, HD_ACCOUNT);
  }
  return state.holdings;
}
function hdById(id) { return hdData().find((r) => String(r.id) === String(id)) || null; }
function hdPrice(r) { return r.price == null ? r.cost : r.price; }
function hdMv(r) { return Math.round(hdPrice(r) * Number(r.shares || 0)); }
function hdShare(r) { const t = (state.hdAccount && state.hdAccount.total) || HD_CAP.total; return hdMv(r) / t * 100; }
function hdPnl(r) { return r.price == null ? null : Math.round((r.price - r.cost) * r.shares); }
function hdPnlPct(r) { return r.price == null || !r.cost ? null : (r.price / r.cost - 1) * 100; }
function hdStopDist(r) { return r.price == null || !r.stop ? null : (r.price / r.stop - 1) * 100; }
function hdMoney(v) { return v == null ? '—' : Number(v).toLocaleString('zh-CN'); }
function hdPct(v, digits) {
  if (v == null) return '—';
  const d = digits == null ? 2 : digits;
  return (v > 0 ? '+' : '') + v.toFixed(d) + '%';
}
function hdPnlCls(v) { return v == null ? 'dim' : v > 0 ? 'wo-up' : v < 0 ? 'wo-down' : 'dim'; }
function hdTotalMv() { return hdData().reduce((s, r) => s + hdMv(r), 0); }
function hdCash() { const a = state.hdAccount || {}; return a.cash == null ? Math.max(0, (a.total || 0) - hdTotalMv()) : a.cash; }
function hdTotalShare() { return hdTotalMv() / ((state.hdAccount && state.hdAccount.total) || 1) * 100; }
function hdTodayPnl() {
  return hdData().reduce((s, r) => (r.today == null ? s : s + hdMv(r) * r.today / (100 + r.today)), 0);
}

/* 四条红线：内部代号只出现在括号里，主文案说人话 */
function hdReds(r) {
  const share = hdShare(r);
  const off = r.price == null;
  const dist = hdStopDist(r);
  const c1 = off ? 'off' : share > HD_CAP.total ? 'bad' : share > HD_CAP.gradeA ? 'todo' : 'done';
  const c2 = off || r.dd == null ? 'off' : r.dd <= -HD_CAP.drawdown ? 'bad' : r.dd <= -HD_CAP.drawdown * 0.3 ? 'todo' : 'done';
  const c3 = off ? 'off' : r.price < r.stop ? 'bad' : dist != null && dist < 3 ? 'todo' : 'done';
  const k = off || !r.trail ? 'off' : r.trail.hit ? 'todo' : 'done';
  return [
    { name: '单票仓位', code: 'C1', st: c1, cur: share.toFixed(1) + '%', limit: '上限 ' + HD_CAP.gradeA + '%（硬顶 ' + HD_CAP.total + '%）', plain: c1 === 'bad' ? '单票超过硬顶，必须先减' : c1 === 'todo' ? '单票超过 A 级上限，建议减一档' : c1 === 'done' ? '单票占比在上限内' : '无行情，未计算' },
    { name: '最大回撤', code: 'C2', st: c2, cur: r.dd == null ? '—' : r.dd.toFixed(1) + '%', limit: '触发线 -' + HD_CAP.drawdown + '%', plain: c2 === 'bad' ? '回撤已到触发线' : c2 === 'todo' ? '回撤偏大，注意收敛' : c2 === 'done' ? '回撤在可承受范围' : '无行情，未计算' },
    { name: '止损线', code: 'C3', st: c3, cur: r.price == null ? '—' : r.price.toFixed(2) + ' / ' + r.stop.toFixed(2), limit: '成本 ×0.92', plain: c3 === 'bad' ? '已跌破止损，今天必须清仓' : c3 === 'todo' ? '接近止损，跌破就走' : c3 === 'done' ? '未触及止损' : '无行情，未计算' },
    { name: '移动止盈', code: 'K139', st: k, cur: r.trail ? r.trail.stage : '未设置', limit: '分档上移止盈', plain: k === 'todo' ? '已到减仓档，按档减' : k === 'done' ? '未到减仓档' : '无移动止盈档位' }
  ];
}
function hdVerdict(r) {
  if (r.price == null) return 'info';
  const reds = hdReds(r);
  if (reds[2].st === 'bad') return 'exit';
  if (r.trail && r.trail.hit) return 'reduce';
  if (reds[0].st !== 'done') return 'reduce';
  if (reds[2].st === 'todo' || r.dd != null && r.dd <= -5) return 'watch';
  return 'hold';
}
const HD_VERDICT = {
  exit: { label: '该走', tone: 'bad', order: 0 },
  reduce: { label: '该减', tone: 'todo', order: 1 },
  watch: { label: '到价了', tone: 'todo', order: 2 },
  hold: { label: '继续拿', tone: 'done', order: 3 },
  info: { label: '待核对', tone: 'off', order: 4 }
};
function hdVerdictPill(v) {
  const m = HD_VERDICT[v] || HD_VERDICT.info;
  return '<span class="state ' + m.tone + '">' + m.label + '</span>';
}
function hdConcl(r) {
  const v = hdVerdict(r);
  if (r.historyEdited) return '成交记录已更新：现持 ' + r.shares + ' 股，均价 ' + r.cost.toFixed(2) + '。仓位与红线已按当前数字检查；原 AI 判断和买卖计划仍需核对。';
  const authored = r.concls && (r.concls[v] || r.concls.info);
  if (authored) return authored;
  /* 人工录入 / OCR 新建的一笔没有预写结论，这里用红线实况拼一句，不留空白 */
  const hot = hdReds(r).filter((x) => x.st === 'bad' || x.st === 'todo');
  if (hot.length) return hot.map((x) => x.plain).join('；') + '。价位和动作在下面三行。';
  return '刚记的一笔：成本 ' + r.cost.toFixed(2) + '，止损 ' + r.stop.toFixed(2) + '，第一档止盈 ' + r.tp.toFixed(2) + '，四条红线都没踩，先按计划拿着。';
}
function hdRedDot(r) {
  const worst = hdReds(r).reduce((acc, x) => (['bad', 'todo', 'off', 'done'].indexOf(x.st) < acc ? acc : ['bad', 'todo', 'off', 'done'].indexOf(x.st)), 9);
  return worst === 0 ? 'err' : worst === 1 ? 'warn' : worst === 2 ? 'info' : 'ok';
}
function hdTodo() { return hdData().filter((r) => ['exit', 'reduce'].indexOf(hdVerdict(r)) >= 0); }
function hdVisible() {
  const rows = hdData().filter((r) => {
    const v = hdVerdict(r);
    if (state.hdView === 'todo') return v === 'exit' || v === 'reduce';
    if (state.hdView === 'check') return v === 'info';
    return true;
  });
  return rows.sort((a, b) => {
    const d = HD_VERDICT[hdVerdict(a)].order - HD_VERDICT[hdVerdict(b)].order;
    return d !== 0 ? d : hdShare(b) - hdShare(a);
  });
}

/* ---------- 行内表单（就地记录人工成交） ---------- */
const HD_OPS = {
  add: { title: '记录加仓', verb: '加仓', kind: 'add' },
  reduce: { title: '记录减仓', verb: '减仓', kind: 'reduce' },
  exit: { title: '记录清仓', verb: '清仓', kind: 'exit' },
  cost: { title: '修正成本', verb: '修正成本', kind: 'cost' }
};
function hdFormOpen(id, kind) { return state.hdForm && String(state.hdForm.id) === String(id) && state.hdForm.kind === kind; }
function hdSharesAfter(r, kind, v) {
  if (kind === 'add') return r.shares + v;
  if (kind === 'exit') return 0;
  if (kind === 'reduce') return r.shares - v;
  return r.shares;
}
function hdCostAfter(r, kind, v, price) {
  if (kind === 'add') return (r.cost * r.shares + price * v) / (r.shares + v);
  if (kind === 'cost') return v;
  return r.cost;
}
/* 对齐生产 positionWarnings：A 级单票 / C1 集中度 / C2 总仓位 / E2 防御期软上限 */
function hdWarns(r, kind, sharesAfter, price) {
  const total = state.hdAccount.total;
  if (!total || !sharesAfter) return [];
  const out = [];
  const share = (sharesAfter * price) / total * 100;
  const rest = (hdTotalMv() - hdMv(r) + sharesAfter * price) / total * 100;
  if (share > HD_CAP.gradeA) out.push('这一笔单票仓位将达 ' + share.toFixed(1) + '%，超过 A 级上限 ' + HD_CAP.gradeA + '%');
  if (share > HD_CAP.total) out.push('这一笔单票仓位将达 ' + share.toFixed(1) + '%，超过 C1 硬顶 ' + HD_CAP.total + '%');
  if (rest > HD_CAP.total) out.push('做完之后总仓位将达 ' + rest.toFixed(1) + '%，超过 C2 上限 ' + HD_CAP.total + '%');
  if (state.hdAccount.index < HD_CAP.indexBar && rest > HD_CAP.softCap) {
    out.push('现在是防御期（沪指 ' + state.hdAccount.index.toFixed(0) + ' < ' + HD_CAP.indexBar + '），总仓位软上限只有 ' + HD_CAP.softCap + '%，做完之后是 ' + rest.toFixed(1) + '%');
  }
  if (kind === 'add' && r.cost) {
    const newCost = hdCostAfter(r, 'add', sharesAfter - r.shares, price);
    if (price < newCost * HD_CAP.c3) out.push('成交价 ' + price + ' 低于 C3 止损位（成本 ' + newCost.toFixed(2) + ' × 0.92 = ' + (newCost * HD_CAP.c3).toFixed(2) + '），属于跌破止损线加仓');
  }
  return out;
}
function hdFieldsText(r, kind, v) {
  if (kind === 'cost') return '修正后成本 ' + v.cost_price + ' 元（原 ' + r.cost.toFixed(2) + '）\n原因 ' + v.reason;
  const shares = kind === 'exit' ? r.shares : v.shares;
  const remain = hdSharesAfter(r, kind, Number(shares || 0));
  return (kind === 'add' ? '成交价 ' : '卖出价 ') + v.price + ' × ' + shares + ' 股' +
    (kind === 'reduce' || kind === 'exit' ? '\n做完之后剩余 ' + remain + ' 股（' + Math.floor(remain / 100) + ' 手）' : '') +
    '\n日期 ' + v.trade_date + '\n备注 ' + (v.note || '（无）');
}
function hdFormHtml(r, kind) {
  const op = HD_OPS[kind];
  const dr = (state.hdForm && String(state.hdForm.id) === String(r.id) && state.hdForm.draft) || {};
  const f = {
    price: dr.price != null ? dr.price : (r.price == null ? '' : r.price.toFixed(2)),
    shares: dr.shares != null ? dr.shares : (kind === 'exit' ? r.shares : ''),
    date: dr.date || '2026-11-16',
    note: dr.note || '',
    cost: dr.cost || '',
    reason: dr.reason || ''
  };
  if (kind === 'cost') {
    return '<div class="hd-form">' +
      '<div class="hd-form-title">' + op.title + ' <span class="hint">只改成本，不产生成交</span></div>' +
      '<label class="hd-field"><span>修正后成本 *</span><input class="input" id="hd-f-cost" type="number" step="0.01" value="' + esc(String(f.cost)) + '" placeholder="' + r.cost.toFixed(2) + '"></label>' +
      '<label class="hd-field wide"><span>修正原因 *（必填，会写进流水）</span><input class="input" id="hd-f-reason" value="' + esc(f.reason) + '" placeholder="例如：交割单录入时把 34.20 打成 33.20"></label>' +
      hdFormActions(r, kind) + '</div>';
  }
  return '<div class="hd-form">' +
    '<div class="hd-form-title">' + op.title + ' <span class="hint">' + esc(r.name) + ' · 现持 ' + r.shares + ' 股 · 成本 ' + r.cost.toFixed(2) + '</span></div>' +
    '<label class="hd-field"><span>' + (kind === 'add' ? '成交价 *' : '卖出价 *') + '</span><input class="input" id="hd-f-price" type="number" step="0.01" value="' + esc(String(f.price)) + '"></label>' +
    (kind === 'exit'
      ? '<label class="hd-field"><span>清仓股数（自动取全部）</span><input class="input" id="hd-f-shares" type="number" value="' + f.shares + '" readonly></label>'
      : '<label class="hd-field"><span>' + (kind === 'add' ? '加仓股数 *（100 整数倍）' : '减仓股数 *（≤ ' + r.shares + '）') + '</span><input class="input" id="hd-f-shares" type="number" step="100" min="100" value="' + esc(String(f.shares)) + '" placeholder="' + (kind === 'add' ? '300' : '400') + '"></label>') +
    '<label class="hd-field"><span>成交日期 *</span><input class="input" id="hd-f-date" type="date" value="' + esc(String(f.date)) + '"></label>' +
    '<label class="hd-field wide"><span>备注</span><input class="input" id="hd-f-note" value="' + esc(f.note) + '" placeholder="' + (kind === 'exit' ? '清仓原因，会带进复盘' : '可不填') + '"></label>' +
    hdFormActions(r, kind) + '</div>';
}
function hdFormActions(r, kind) {
  const confirming = state.hdForm && state.hdForm.confirm;
  return '<div class="hd-form-acts"><button class="btn sm" data-action="hd-op-cancel" data-hd="' + r.id + '">取消</button>' +
    (confirming ? '<span class="hint">上面已列出风险，核对后确认</span>' : '<span class="hint">提交前会再让你核对一次</span>') +
    '<button class="btn ' + (kind === 'exit' ? 'danger' : 'primary') + ' sm" data-action="hd-op-ok" data-hd="' + r.id + '" data-kind="' + kind + '">提交</button></div>';
}
function hdConfirmHtml(r, kind, v) {
  const warns = v.warns || [];
  const shares = kind === 'cost' ? r.shares : (kind === 'exit' ? r.shares : Number(v.shares));
  const remain = kind === 'cost' ? r.shares : hdSharesAfter(r, kind, shares);
  return '<div class="inline-confirm' + (kind === 'exit' ? ' danger' : '') + '">' +
    '<div class="ic-title">确认' + HD_OPS[kind].title.replace('记录', '') + '？</div>' +
    (warns.length ? '<div class="hd-warns">' + warns.map((w) => '<div class="hd-warn">' + icon('alert', 'sm') + esc(w) + '</div>').join('') + '</div>' : '') +
    '<div class="ic-desc">' + esc(v.fields).replace(/\n/g, ' ') + '</div>' +
    '<div class="hd-confirm-rule">' + icon('shield', 'sm') + '<div>这一步只记录你人工成交的结果，系统不会下单。确认后 C3 止损 / 移动止盈 / +5% / +10% 档位按知识库规则自动重算，并重算单票与总仓位占比（留痕可在流水里查）。</div></div>' +
    '<div class="ic-actions"><button class="btn sm" data-action="hd-op-cancel" data-hd="' + r.id + '">返回改数字</button>' +
      '<button class="btn ' + (kind === 'exit' ? 'danger' : 'primary') + ' sm" data-action="hd-op-confirm" data-hd="' + r.id + '" data-kind="' + kind + '">确认记录</button></div>' +
    (remain === 0 ? '<div class="hint" style="margin-top:8px">清仓后这笔会自动进入复盘队列，' + esc(r.name) + ' 的持仓记录改为已离场。</div>' : '') +
  '</div>';
}
/* 读表单 + 校验，返回 null 表示被拦下（与生产 rules 一致） */
function hdReadForm(r, kind) {
  const num = (id) => { const el = $('#' + id); return el ? el.value : ''; };
  if (kind === 'cost') {
    const cost = parseFloat(num('hd-f-cost'));
    const reason = (num('hd-f-reason') || '').trim();
    if (!Number.isFinite(cost) || !(cost > 0)) { toast('成本价要填正数', '修正成本只改成本，不产生成交。', 'warn'); return null; }
    if (!reason) { $('#' + 'hd-f-reason').focus(); toast('必须填写修正原因', '不写原因，后面没人知道这笔成本为什么变了。', 'warn'); return null; }
    return { cost_price: cost, reason: reason, shares: r.shares, warns: [], fields: hdFieldsText(r, kind, { cost_price: cost.toFixed(2), reason: reason }) };
  }
  const price = parseFloat(num('hd-f-price'));
  const shares = kind === 'exit' ? r.shares : parseInt(num('hd-f-shares'), 10);
  const date = num('hd-f-date') || '2026-11-16';
  const note = (num('hd-f-note') || '').trim();
  if (!(price > 0)) { toast('成交价要填正数', '价格取当前现价也可以，但不能空着。', 'warn'); return null; }
  if (kind !== 'exit') {
    if (!(shares > 0)) { toast('股数要填', '减仓股数不能超过持仓。', 'warn'); return null; }
    if (shares % 100 !== 0) { toast('股数必须是 100 的整数倍', 'A 股一手 100 股，你填的是 ' + shares + '。', 'warn'); return null; }
  }
  if (kind === 'reduce' && shares >= r.shares) { toast('减仓不能减完', '要全部走请用「清仓」，只有清仓会把这笔转成已离场并触发复盘。', 'warn'); return null; }
  if (kind !== 'add' && shares > r.shares) { toast('卖出股数超过持仓', '当前持仓 ' + r.shares + ' 股。', 'warn'); return null; }
  const after = hdSharesAfter(r, kind, shares);
  return {
    price: price, shares: shares, trade_date: date, note: note,
    warns: hdWarns(r, kind, after, price),
    fields: hdFieldsText(r, kind, { price: price.toFixed(2), shares: shares, trade_date: date, note: note })
  };
}
function hdApplyOp(r, kind, v) {
  const ledger = hdTradeLedger(r), old = r.cost;
  const adjustment = { id: r.id + '-t' + ledger.nextId++, date: ledger.entries.map(t => t.date).concat('2026-11-16').sort().pop(), order: Math.max(...ledger.entries.map(t => t.order)) + 1, side: 'adjust', amount: hdTradeRound((Number(v.cost_price) - old) * r.shares), status: 'active', note: '成本由 ' + old.toFixed(2) + ' 修正为 ' + Number(v.cost_price).toFixed(2) + '：' + v.reason };
  ledger.entries.push(adjustment); ledger.version++;
  ledger.audit.unshift({ at: new Date().toLocaleString('zh-CN'), reason: v.reason, changes: [{ before: null, after: clone(adjustment) }] });
  r.cost = Number(v.cost_price); r.stop = Math.round(r.cost * HD_CAP.c3 * 100) / 100; r.historyEdited = true;
  r.trades.unshift({ side: 'sys', shares: 0, price: 0, date: adjustment.date, note: '成本由 ' + old.toFixed(2) + ' 修正为 ' + r.cost.toFixed(2) + '：' + v.reason });
  return '成本已修正为 ' + r.cost.toFixed(2) + '，止损位跟着重算到 ' + r.stop.toFixed(2);
}

/* ---------- 详情 Tab ---------- */
function hdConclTab(r) {
  const v = hdVerdict(r);
  const dist = hdStopDist(r);
  const reds = hdReds(r);
  const triggered = reds.filter((x) => x.st === 'bad' || x.st === 'todo');
  return '<div class="hd-concl ' + (v === 'exit' ? 'bad' : v === 'info' ? 'off' : 'warn') + '">' +
      '<div class="hd-concl-tag">' + hdVerdictPill(v) + '<b>' + esc(r.name) + '</b><span class="hint">' + esc(v === 'exit' ? '今天要动手' : v === 'reduce' ? '今天要动手' : v === 'watch' ? '到价再说' : v === 'hold' ? '今天不动' : '先补数据') + '</span></div>' +
      '<div class="hd-concl-txt">' + esc(hdConcl(r)) + '</div>' +
      (triggered.length ? '<div class="hd-concl-reds">' + triggered.map((x) =>
        '<button class="hd-red" data-action="hd-tab" data-tab="risk"><span class="state ' + x.st + '"></span>' + esc(x.name) + '：' + esc(x.plain) + '</button>').join('') + '</div>' : '') +
    '</div>' +
    '<dl class="kv">' +
      '<dt>现价 / 加权成本</dt><dd class="mono">' + (r.price == null ? '<span class="dim">未取到行情</span>' : r.price.toFixed(2) + ' / ' + r.cost.toFixed(2)) + '</dd>' +
      '<dt>持股 / 市值</dt><dd class="mono">' + r.shares + ' 股 · ' + hdMoney(hdMv(r)) + ' 元（占总资产 ' + hdShare(r).toFixed(1) + '%）</dd>' +
      '<dt>浮动盈亏</dt><dd><span class="mono ' + hdPnlCls(hdPnl(r)) + '">' + hdMoney(hdPnl(r)) + ' 元（' + hdPct(hdPnlPct(r)) + '）</span>' + (r.today == null ? '' : ' <span class="hint">今日 ' + hdPct(r.today) + '</span>') + '</dd>' +
      '<dt>止损 / 距止损</dt><dd class="mono">' + r.stop.toFixed(2) + ' <span class="' + (dist != null && dist < 3 ? 'wo-down' : 'hint') + '">' + (dist == null ? '' : '距 ' + dist.toFixed(1) + '%') + '</span></dd>' +
      '<dt>止盈 / 目标仓位</dt><dd class="mono">' + r.tp.toFixed(2) + ' · ' + r.targetPct + '%' + (r.suggestPct === 0 ? ' <span class="wo-down">建议降到 0（该走）</span>' : ' <span class="hint">防御期建议 ' + r.suggestPct + '%</span>') + '</dd>' +
      '<dt>来源</dt><dd>' + (r.plan ? '建仓计划 #' + r.plan.id + ' · <button class="btn link xs" data-nav="#/candidates?date=' + r.plan.batch + '">' + esc(r.plan.batch) + ' 候选池 ' + icon('arrow', 'sm') + '</button>' : '<span class="dim">人工录入，未绑定建仓计划</span>') + '</dd>' +
    '</dl>' +
    (r.scenes ? '<div class="cp-scene"><div class="cp-scene-head"><span class="cp-scene-title">怎么做</span><span class="hint">按现价 ' + (r.price == null ? '—' : r.price.toFixed(2)) + ' 算的三个走法</span></div>' +
      r.scenes.map((s) => '<div class="cp-sc ' + s.k + '"><div class="cp-sc-tag">' + icon(s.k === 'up' ? 'caretUp' : s.k === 'dn' ? 'caretDown' : 'minus', 'sm') +
        (s.k === 'up' ? '如果继续涨' : s.k === 'dn' ? '如果下跌' : '如果横盘') + '</div>' +
        '<div class="cp-sc-cond">' + esc(s.c) + '</div><div class="cp-sc-act">' + esc(s.a) + '</div></div>').join('') + '</div>'
      : '<div class="cp-scene"><div class="cp-scene-empty">没有行情就没有价位计算，也就不给结论。点上面的「刷新行情」重取，或在「买卖记录」里核对成本与股数。</div></div>') +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>这一页只回答「手上的票现在怎么办」。要买的新票在每日候选池；这里不重复给买入建议。</div></div>';
}

function hdDecisionCard(r, d, showActs) {
  if (!d) {
    if (r.price == null) return '<div class="cp-scene-empty">没有行情，卖出决策不计算。刷新行情后会自动补。</div>';
    return '<div class="cp-scene-empty">这笔还没有卖出决策。后台跑一次（sell_decision）就有结论，会告诉你：要不要走、按什么减仓、各维度的归因、执行价位区间和动手前自检。</div>' +
      (showActs ? '<div class="hd-decide-acts"><button class="btn primary sm" data-action="hd-decision" data-hd="' + r.id + '">' + icon('chart', 'sm') + '生成卖出决策</button>' +
        '<span class="hint">决策只是参考，卖出必须由你人工执行；执行完了回到「买卖记录」把成交记下来。</span></div>' : '');
  }
  const actMap = { hold: '继续持有', reduce: '减仓', partial: '部分减仓', exit: '清仓', sell: '卖出清仓' };
  const confMap = { high: '高', medium: '中', low: '低' };
  const isPartial = d.action === 'partial' && d.ratio;
  const sellShares = isPartial ? Math.min(r.shares, Math.max(100, Math.ceil((r.shares * d.ratio) / 100) * 100)) : 0;
  return '<div class="hd-sug">' +
    '<div class="hd-sug-head"><b>卖出决策：' + esc(actMap[d.action] || d.action) + '</b>' +
      (d.running ? '<span class="state run"></span><span class="hd-running">后台计算中（sell_decision）</span>' : tag('置信度 ' + (confMap[d.conf] || d.conf), d.conf === 'high' ? 'red' : 'outline')) +
      '<span class="spacer"></span><span class="hint">' + esc(d.at) + ' 生成</span></div>' +
    (d.running ? '<div class="cp-scene-empty">这一版先把「跑完会看到什么」画出来：结论、置信度、按什么减仓、各维度归因、风险提示和卖出前检查清单。完成后刷新即替换，不会覆盖成空白。</div>' : '') +
    (d.running ? '' : (isPartial ? '<div class="hd-sug-cut">' + icon('minus', 'sm') + '建议减 ' + Math.round(d.ratio * 100) + '%　<span class="mono">' + r.shares + ' 股 → 卖 ' + sellShares + ' 股（' + Math.floor(sellShares / 100) + ' 手）→ 剩 ' + (r.shares - sellShares) + ' 股</span></div>' : '')) +
    (d.final ? '<div class="hd-sug-final">' + esc(d.final) + '</div>' : '') +
    '</div>' +
    (d.dims ? '<div class="hd-dims">' + d.dims.map((dm) => {
      const color = dm.verdict === '支持' ? 'var(--up)' : dm.verdict === '风险' ? 'var(--warn)' : 'var(--text-3)';
      return '<div class="hd-dim"><span class="hd-dim-name">' + esc(dm.dim) + '</span>' +
        '<span class="hd-dim-bar"><i style="width:' + Math.max(4, Math.min(100, dm.score)) + '%;background:' + color + '"></i></span>' +
        '<span class="hd-dim-score mono">' + dm.score + '</span>' + tag(dm.verdict, dm.verdict === '支持' ? 'red' : dm.verdict === '风险' ? 'gold' : 'mute') +
        (dm.advice ? '<span class="hd-dim-advice">' + esc(dm.advice) + '</span>' : '') + '</div>';
    }).join('') + '</div>' : '') +
    (d.reasons ? '<div class="cp-list-title" style="margin-top:14px">为什么这么判</div><ol class="hd-reasons">' + d.reasons.map((x) => '<li>' + esc(x) + '</li>').join('') + '</ol>' : '') +
    (d.zone || d.risk ? '<dl class="kv" style="margin-top:10px">' +
      (d.zone ? '<dt>执行价位区间</dt><dd class="mono">' + esc(d.zone) + '</dd>' : '') +
      (d.risk ? '<dt>风险提示</dt><dd class="hd-risk">' + esc(d.risk) + '</dd>' : '') + '</dl>' : '') +
    (d.checks ? '<div class="cp-list-title" style="margin-top:14px">动手前自检</div><ul class="hd-checks">' + d.checks.map((c) =>
      '<li class="' + (c.ok ? 'ok' : 'no') + '">' + icon(c.ok ? 'check' : 'alert', 'sm') + esc(c.label) + '</li>').join('') + '</ul>' : '') +
    (showActs ? '<div class="hd-decide-acts">' +
      (d.running ? '<span class="hd-task"><span class="state run"></span>任务 sell_decision 已提交，跑完刷新这一页就有结论</span>' :
        r.decision ? '<button class="btn sm" data-action="hd-decision" data-hd="' + r.id + '">' + icon('rotate', 'sm') + '重新生成</button>' :
        '<button class="btn primary sm" data-action="hd-decision" data-hd="' + r.id + '">' + icon('chart', 'sm') + '生成卖出决策</button>') +
      '<span class="hint">决策只是参考，卖出必须由你人工执行；执行完了回到「买卖记录」把成交记下来。</span></div>' : '');
}

function hdBasisTab(r) {
  const hist = r.decisions || [];
  return hdDecisionCard(r, r.decision, true) +
    '<div class="cp-list-title" style="margin-top:16px">历史决策（' + hist.length + '）</div>' +
    (hist.length ? '<div class="hd-hist">' + hist.map((h, i) => {
      const actMap = { hold: '继续持有', reduce: '减仓', partial: '部分减仓', exit: '清仓' };
      const open = i === 0 && state.hdHistOpen;
      return '<div class="hd-hist-item' + (open ? ' open' : '') + '">' +
        '<button class="hd-hist-head" data-action="hd-hist-toggle"><span class="mono dim">' + esc(h.at) + '</span>' +
          '<b>' + esc(actMap[h.action] || h.action) + '</b>' + tag('置信 ' + ({ high: '高', medium: '中', low: '低' }[h.conf] || h.conf), h.conf === 'high' ? 'red' : 'outline') +
          '<span class="spacer"></span><span class="dim">' + esc(h.one) + '</span>' + icon('chevron', 'sm') + '</button>' +
        (open ? '<div class="hd-hist-body">' + esc(h.one) + '（正式页面这一层展开的是完整决策体，与上方同一套渲染）</div>' : '') +
        '</div>';
    }).join('') + '</div>' : '<div class="wo-empty" style="padding:12px 0">还没有历史决策。</div>') +
    '<div class="cap-note" style="margin-top:14px">' + icon('info') + '<div>生成卖出决策走后台任务 <code>sell_decision</code>，跑完自动回到这一层，不用守着页面。它读的维度与打分口径和候选池评分同源。</div></div>';
}

function hdTradeRound(n) { return Math.round((n + Number.EPSILON) * 100000000) / 100000000; }
function hdTradeDate(s) {
  return /^\d{4}-\d{2}-\d{2}$/.test(s) && Number.isFinite(Date.parse(s)) && new Date(s).toISOString().slice(0, 10) === s;
}
function hdTradeReplay(entries) {
  let shares = 0, basis = 0, realized = 0, cashFlow = 0, buyAmount = 0;
  const steps = [], errors = [];
  const active = entries.filter(t => t.status !== 'void').slice().sort((a, b) => a.date.localeCompare(b.date) || a.order - b.order);
  active.forEach(t => {
    if (!hdTradeDate(t.date)) { errors.push('记录 ' + t.order + ' 的日期无效。'); return; }
    if (t.side === 'adjust') {
      if (shares) basis = hdTradeRound(basis + t.amount);
      else realized = hdTradeRound(realized - t.amount);
      if (basis < 0) errors.push(t.date + ' 的成本调整会使成本小于零，请先核对历史。');
    } else {
      const amount = hdTradeRound(t.price * t.shares), cost = shares ? basis / shares : 0;
      if (t.side === 'buy') { basis = hdTradeRound(basis + amount); shares += t.shares; cashFlow -= amount; buyAmount += amount; }
      else if (t.shares > shares) { errors.push(t.date + ' · 顺序 ' + t.order + ' 卖出 ' + t.shares + ' 股，但当时只有 ' + shares + ' 股；请补齐买入或调整同日顺序。'); return; }
      else { realized = hdTradeRound(realized + amount - cost * t.shares); shares -= t.shares; basis = shares ? hdTradeRound(basis - cost * t.shares) : 0; cashFlow += amount; }
      steps.push({ id: t.id, date: t.date, order: t.order, shares: shares, cost: shares ? basis / shares : 0, realized: realized, saleCost: cost });
    }
  });
  return { shares: shares, cost: shares ? basis / shares : 0, realized: realized, cashFlow: hdTradeRound(cashFlow), buyAmount: buyAmount, steps: steps, errors: errors };
}
function hdTradeLedger(r) {
  if (r.ledger) return r.ledger;
  const entries = r.trades.filter(t => t.side === 'buy' || t.side === 'sell').map((t, i) => Object.assign({}, t, { id: r.id + '-t' + (i + 1), order: i + 1, status: 'active' }));
  const replay = hdTradeReplay(entries);
  const difference = hdTradeRound(r.cost * r.shares - replay.cost * replay.shares);
  if (Math.abs(difference) >= 0.005) entries.push({ id: r.id + '-baseline', order: entries.length + 1, date: entries.map(t => t.date).sort().pop() || r.entry, side: 'adjust', amount: difference, status: 'active', note: '原有成本与成交明细的差额，保留为历史成本调整；不视为买卖，不改变现金。' });
  r.ledger = { entries: entries, version: 0, nextId: entries.length + 1, audit: [] };
  return r.ledger;
}
function hdTradeStock(id) {
  const held = hdById(id);
  if (held) return held;
  const archive = state.exited.find(x => String(x.row ? x.row.id : x.id) === String(id));
  if (!archive) return null;
  if (!archive.row) {
    archive.row = { id: archive.id, code: archive.code, name: archive.name, entry: archive.entry, source: '历史归档', shares: 0, cost: archive.cost, price: archive.out, today: null, dd: null, stop: archive.cost * HD_CAP.c3, tp: archive.cost * 1.15, targetPct: 10, suggestPct: 10, trail: null, plan: null, alerts: 0, rules: [], concls: {}, scenes: null, decision: null, decisions: [], records: [], archiveSummary: true, trades: [
      { side: 'buy', shares: archive.shares, price: archive.cost, date: archive.entry, note: '根据旧归档摘要还原，请按券商明细核对' },
      { side: 'sell', shares: archive.shares, price: archive.out, date: archive.exit, note: archive.note }
    ] };
  }
  return archive.row;
}
function hdTradeDraft(r) {
  if (!state.hdTradeDrafts[r.id]) {
    const ledger = hdTradeLedger(r);
    state.hdTradeDrafts[r.id] = { entries: clone(ledger.entries), version: ledger.version, nextId: ledger.nextId, editing: [], reason: '', paste: '', errors: [], preview: null, duplicatesOk: false };
  }
  return state.hdTradeDrafts[r.id];
}
function hdTradeAdd(r, kind) {
  const d = hdTradeDraft(r), seq = d.nextId++;
  const t = { id: r.id + '-t' + seq, date: d.entries.map(t => t.date).filter(hdTradeDate).concat('2026-11-16').sort().pop(), order: Math.max(0, ...d.entries.map(t => Number(t.order) || 0)) + 1, side: kind === 'reduce' || kind === 'exit' ? 'sell' : 'buy', price: '', shares: '', note: '', status: 'active' };
  if (kind) { t.price = hdPrice(r); t.shares = kind === 'exit' ? r.shares : kind === 'reduce' ? Math.min(100, r.shares) : 100; }
  d.entries.push(t); d.editing.push(t.id); d.preview = null; d.errors = []; d.duplicatesOk = false;
  return t;
}
function hdTradeChanges(r, entries) {
  const old = hdTradeLedger(r).entries;
  return entries.filter(t => !old.some(o => o.id === t.id && JSON.stringify(o) === JSON.stringify(t))).map(t => ({ before: old.find(o => o.id === t.id) || null, after: t }));
}
function hdTradePreview(r, d) {
  const errors = [], entries = clone(d.entries), ledger = hdTradeLedger(r);
  if (d.version !== ledger.version) errors.push('记录已经更新，请放弃旧草稿后重新修改。');
  entries.forEach((t, i) => {
    if (t.side === 'adjust' || t.status === 'void') return;
    t.price = Number(t.price); t.shares = Number(t.shares); t.order = Number(t.order); t.note = t.note.trim();
    if (!hdTradeDate(t.date)) errors.push('第 ' + (i + 1) + ' 行：请填写有效日期。');
    if (!['buy', 'sell'].includes(t.side)) errors.push('第 ' + (i + 1) + ' 行：方向只能是买入或卖出。');
    if (!Number.isFinite(t.price) || !(t.price > 0) || !Number.isFinite(t.price * t.shares) || t.price * t.shares > Number.MAX_SAFE_INTEGER) errors.push('第 ' + (i + 1) + ' 行：成交价或成交金额无效。');
    if (!Number.isSafeInteger(t.shares) || t.shares <= 0) errors.push('第 ' + (i + 1) + ' 行：股数必须是正整数，不能填小数。');
    if (!Number.isSafeInteger(t.order) || t.order <= 0) errors.push('第 ' + (i + 1) + ' 行：同日顺序必须是正整数。');
  });
  const active = entries.filter(t => t.status !== 'void');
  const orderKeys = new Set();
  active.forEach(t => { const key = t.date + '/' + t.order; if (orderKeys.has(key)) errors.push(t.date + ' 的同日顺序 ' + t.order + ' 重复，请为先发生的一笔填更小的数字。'); orderKeys.add(key); });
  const changes = hdTradeChanges(r, entries);
  if (!changes.length) errors.push('还没有待保存的变更，可以新增一行或修改历史成交。');
  if (changes.some(c => c.before) && !d.reason.trim()) errors.push('修改或作废历史成交时，必须填写本次调整原因。');
  const after = errors.length ? null : hdTradeReplay(entries);
  if (after) {
    errors.push(...after.errors);
    if (after.shares && hdData().some(x => x.id !== r.id && x.code === r.code)) errors.push('此股票已有另一条在持仓记录，不能从归档恢复为重复持仓；请先核对并合并实际成交。');
  }
  d.errors = [...new Set(errors)]; d.preview = null;
  if (errors.length) return;
  const before = hdTradeReplay(ledger.entries);
  const duplicates = changes.filter(c => c.after.side !== 'adjust' && c.after.status !== 'void' && active.some(o => o.id !== c.after.id && o.side === c.after.side && o.date === c.after.date && o.price === c.after.price && o.shares === c.after.shares));
  const cash = hdTradeRound(hdCash() + after.cashFlow - before.cashFlow);
  const total = hdTradeRound(state.hdAccount.total + cash - hdCash() + (after.shares - r.shares) * hdPrice(r));
  d.preview = { entries: entries, before: before, after: after, changes: changes, cash: cash, total: total, duplicates: duplicates.length, account: JSON.stringify(state.hdAccount) };
}
function hdTradeCommit(r, d) {
  const p = d.preview, ledger = hdTradeLedger(r);
  if (!p || ledger.version !== d.version || p.account !== JSON.stringify(state.hdAccount)) { d.preview = null; d.errors = ['账户或成交记录已变化，请重新预览后确认。']; return false; }
  if (p.duplicates && !d.duplicatesOk) { d.errors = ['请先确认相同日期、价格和股数的记录确实是不同成交；不会自动忽略任何一笔。']; return false; }
  ledger.audit.unshift({ at: new Date().toLocaleString('zh-CN'), reason: d.reason.trim() || '补录实际成交', changes: clone(p.changes) });
  ledger.entries = clone(p.entries); ledger.version++; ledger.nextId = d.nextId;
  r.shares = p.after.shares; r.cost = p.after.cost; r.realized = p.after.realized; r.historyEdited = true;
  r.trades = ledger.entries.filter(t => t.status !== 'void' && t.side !== 'adjust').map(t => clone(t)).concat(r.trades.filter(t => t.side === 'sys'));
  r.records = ledger.entries.filter(t => t.status !== 'void' && t.side !== 'adjust').map(t => ({ date: t.date, price: t.price, shares: t.side === 'buy' ? t.shares : -t.shares, created: '人工维护', status: '当前有效' }));
  r.entry = ledger.entries.filter(t => t.side === 'buy' && t.status !== 'void').map(t => t.date).sort()[0] || r.entry;
  state.hdAccount.cash = p.cash; state.hdAccount.total = p.total;
  const oldArchive = state.exited.find(x => x.row === r);
  state.exited = state.exited.filter(x => x.row !== r);
  if (!r.shares) {
    const sales = ledger.entries.filter(t => t.side === 'sell' && t.status !== 'void').sort((a, b) => a.date.localeCompare(b.date) || a.order - b.order);
    const last = sales[sales.length - 1];
    const step = last && p.after.steps.find(s => s.id === last.id);
    state.holdings = state.holdings.filter(x => x.id !== r.id);
    state.exited.unshift({ id: r.id, row: r, code: r.code, name: r.name, entry: r.entry, exit: last ? last.date : '无有效成交', shares: last ? last.shares : 0, cost: step ? step.saleCost : 0, out: last ? last.price : 0, pnl: p.after.buyAmount ? p.after.realized / p.after.buyAmount * 100 : 0, realized: p.after.realized, note: last ? '已按有效成交重算' : '记录已全部作废', reviewId: oldArchive ? oldArchive.reviewId : null });
    state.hdView = 'exited'; state.hdArchiveId = r.id;
  } else {
    if (!state.holdings.some(x => x.id === r.id)) state.holdings.push(r);
    state.hdView = 'all'; state.hdId = r.id; state.hdTab = 'ops';
  }
  delete state.hdTradeDrafts[r.id];
  return true;
}
function hdTradeDescribe(t) {
  if (!t) return '未录入';
  return t.date + ' · 顺序 ' + t.order + ' · ' + (t.side === 'adjust' ? '成本调整 ' + t.amount.toFixed(2) + ' 元' : (t.side === 'buy' ? '买入 ' : '卖出 ') + t.shares + ' 股 × ' + Number(t.price).toFixed(2) + ' 元') + (t.status === 'void' ? ' · 已作废' : '') + (t.note ? ' · ' + t.note : '');
}
function hdTradePreviewHtml(r, d) {
  const p = d.preview, num = n => n == null ? '无行情' : hdMoney(Number(n.toFixed(2)));
  const b = p.before, a = p.after;
  const floating = v => v.shares === 0 ? 0 : r.price == null ? null : (r.price - v.cost) * v.shares;
  return '<section class="hd-trade-preview" aria-label="保存前影响预览"><h4>保存前，再核对一下 · ' + esc(r.name) + '</h4><p class="hint">' + p.changes.length + ' 笔变更，后续每笔成交已按日期和同日顺序重新计算。尚未保存。</p>' +
    '<div class="hd-trade-impact">' + [['持股（股）', b.shares, a.shares], ['持仓均价（元）', b.cost, a.cost], ['累计已实现盈亏（元）', b.realized, a.realized], ['当前浮动盈亏（元）', floating(b), floating(a)], ['账户现金（元）', hdCash(), p.cash], ['账户总资产（元）', state.hdAccount.total, p.total]].map(x => '<div><span>' + x[0] + '</span><b class="mono">' + num(x[1]) + ' → ' + num(x[2]) + '</b></div>').join('') + '</div>' +
    (a.shares === 0 ? '<p class="hd-warns">保存后不再持有，将移至「已离场」；仍可修改或作废历史记录。</p>' : !hdById(r.id) ? '<p class="hd-warns">保存后恢复 ' + a.shares + ' 股，重新进入持仓监控；原归档报价不是实时行情。</p>' : '') +
    (p.cash < 0 ? '<p class="hd-warns">按录入成交计算，现金将为负数。请核对券商资金及账户基线；不会把差额自动抹成零。</p>' : '') +
    '<details open><summary>本次变更（修改前 / 修改后）</summary><div class="hd-trade-changes">' + p.changes.map(c => '<div><span>原：' + esc(hdTradeDescribe(c.before)) + '</span><b>新：' + esc(hdTradeDescribe(c.after)) + '</b></div>').join('') + '</div></details>' +
    '<details><summary>重算后的每笔持股、均价和累计已实现盈亏</summary><div class="hd-trade-changes">' + a.steps.map(s => '<div>' + esc(s.date) + ' · 顺序 ' + s.order + ' · ' + s.shares + ' 股 · 均价 ' + num(s.cost) + ' · 已实现 ' + num(s.realized) + ' 元</div>').join('') + '</div></details>' +
    (p.duplicates ? '<label class="hd-trade-duplicate"><input type="checkbox" data-trade-duplicates data-hd="' + r.id + '"' + (d.duplicatesOk ? ' checked' : '') + '>存在相同日期、方向、价格和股数的记录，我已核对它们是不同的真实成交（全部保留）</label>' : '') +
    '<p class="hint">持仓采用移动加权均价；已实现盈亏按每笔卖出时的成本计算，暂不计佣金和税费。止损、止盈计划保留不动，原 AI 判断需重新核对。原型只在本次页面会话中保存，刷新会恢复示例数据；不会下单。</p>' +
    '<div class="hd-ops-bar"><button class="btn primary sm" data-action="hd-ledger-save" data-hd="' + r.id + '">确认保存全部变更</button><button class="btn sm" data-action="hd-ledger-back" data-hd="' + r.id + '">返回继续修改</button></div></section>';
}
function hdTradeTableHtml(r) {
  const ledger = hdTradeLedger(r), d = state.hdTradeDrafts[r.id], entries = d ? d.entries : ledger.entries;
  const button = (action, label, id, extra) => '<button class="btn ' + (extra || 'link xs') + '" data-action="hd-ledger-' + action + '" data-hd="' + r.id + '"' + (id ? ' data-trade="' + esc(id) + '"' : '') + '>' + label + '</button>';
  const errors = d && d.errors.length ? '<div class="hd-warns" role="alert">' + d.errors.map(e => '<div>' + esc(e) + '</div>').join('') + '</div>' : '';
  if (d && d.preview) return errors + hdTradePreviewHtml(r, d);
  const field = (t, key, label, type) => key === 'note' ? '<textarea class="input" rows="2" aria-label="' + label + '" data-trade="' + esc(t.id) + '" data-field="note" data-hd="' + r.id + '">' + esc(t.note) + '</textarea>' : '<input class="input" aria-label="' + label + '" type="' + type + '" data-trade="' + esc(t.id) + '" data-field="' + key + '" data-hd="' + r.id + '" value="' + esc(t[key]) + '"' + (type === 'number' ? ' min="0" step="' + (key === 'price' ? '0.01' : '1') + '"' : '') + '>';
  return '<section class="hd-trade-section"><div class="hd-ops-bar"><b>买卖明细 · ' + esc(r.name) + '</b>' + button('add', '＋ 新增一笔 / 补录', null, 'primary sm') + button('paste-open', '从 Excel 粘贴多笔', null, 'sm') + '</div>' +
    '<p class="hint">当前已保存：' + r.shares + ' 股 · 持仓均价 ' + (r.shares ? r.cost.toFixed(2) : '—') + ' 元 · 累计已实现盈亏 ' + hdMoney(Number(hdTradeReplay(ledger.entries).realized.toFixed(2))) + ' 元。<br>可连续加行，备注格按 Tab 可加下一行，最后一次保存。日期较早的先计算；同一天按「顺序」从小到大，可调整数字。这里只记实际成交，不要求整手，不会自动下单。</p>' +
    (r.archiveSummary ? '<p class="hd-warns">旧归档只有汇总数字，以下买卖为摘要还原，请先按券商明细核对；不代表完整历史。</p>' : '') +
    (entries.some(t => t.side === 'adjust') ? '<p class="hd-warns">此持仓包含历史成本调整，下表单独列出并参与重算，不会伪装成成交或影响现金。</p>' : '') +
    (entries.some(t => /忽略|重复/.test(t.note)) ? '<p class="hd-warns">旧备注含「重复 / 忽略」，但原持股计入了两笔。当前保留原有股数；请核对后作废真正多记的记录，不会仅凭同一天就自动去重。</p>' : '') + errors +
    (d && d.pasteOpen ? '<div class="hd-trade-paste"><label class="hd-field">粘贴 Excel 单元格（按日期、方向、价格、股数、备注五列；可带表头）<textarea class="input" rows="5" data-trade-paste data-hd="' + r.id + '" placeholder="2026-11-12&#9;买入&#9;26.50&#9;100&#9;补录">' + esc(d.paste) + '</textarea></label>' + button('paste', '填入表格（尚未保存）', null, 'sm') + '<span class="hint">日期支持 2026-11-12 或 2026/11/12。也可直接在新行日期格粘贴这五列。</span></div>' : '') +
    '<div class="hd-trade-scroll" tabindex="0" aria-label="买卖明细，可横向滚动"><table class="hd-trade-table"><thead><tr><th>日期</th><th>同日顺序</th><th>方向</th><th>价格 / 元</th><th>股数</th><th>备注</th><th>操作</th></tr></thead><tbody>' + entries.map(t => {
      if (t.side === 'adjust') return '<tr><td>' + esc(t.date) + '</td><td>' + t.order + '</td><td colspan="3">成本调整 ' + t.amount.toFixed(2) + ' 元</td><td colspan="2">' + esc(t.note) + '</td></tr>';
      const original = ledger.entries.find(o => o.id === t.id), editing = d && d.editing.includes(t.id), voided = t.status === 'void';
      const read = !editing || voided;
      return '<tr class="' + (voided ? 'is-void' : editing ? 'is-editing' : '') + '"><td>' + (read ? esc(t.date) : field(t, 'date', '成交日期', 'text')) + '</td><td>' + (read ? t.order : field(t, 'order', '同日顺序', 'number')) + '</td><td>' + (read ? (t.side === 'buy' ? '买入' : '卖出') : '<select class="input" aria-label="买卖方向" data-trade="' + esc(t.id) + '" data-field="side" data-hd="' + r.id + '">' + (!['buy', 'sell'].includes(t.side) ? '<option value="' + esc(t.side) + '" selected>待核对方向</option>' : '') + '<option value="buy"' + (t.side === 'buy' ? ' selected' : '') + '>买入</option><option value="sell"' + (t.side === 'sell' ? ' selected' : '') + '>卖出</option></select>') + '</td><td>' + (read ? Number(t.price).toFixed(2) : field(t, 'price', '成交价格', 'number')) + '</td><td>' + (read ? t.shares : field(t, 'shares', '成交股数', 'number')) + '</td><td>' + (read ? esc(t.note || '—') : field(t, 'note', '成交备注', 'text')) + '</td><td>' +
        (voided ? '已作废' + (original && original.status !== 'void' ? button('undo', '撤销作废', t.id) : '') : (!original ? tag('待新增', 'gold') + button('remove', '移除', t.id) : (editing ? tag('待修改', 'gold') + button('undo', '撤销修改', t.id) : button('edit', '修改', t.id)) + button('void', '作废', t.id))) + '</td></tr>';
    }).join('') + '</tbody></table></div>' +
    (d ? '<label class="hd-field hd-trade-reason">本次调整原因（修改 / 作废历史必填，新增可选）<input class="input" data-trade-reason data-hd="' + r.id + '" value="' + esc(d.reason) + '" placeholder="例如：按券商交割单修正成交价，或之前重复记了一笔"></label><div class="hd-ops-bar">' + button('preview', '预览全部变更', null, 'primary sm') + button('discard', d.discardAsk ? '确认放弃草稿' : '放弃本次草稿', null, 'sm') + (d.discardAsk ? button('keep', '继续编辑', null, 'sm') : '<span class="hint">未保存 · 切换股票或标签仍保留草稿</span>') + '</div>' : '') +
    '<p class="hint">原型演示：数据仅保留至刷新页面；成交金额与盈亏暂不含佣金、税费。</p>' +
    '<details class="hd-trade-audit"><summary>修改留痕（' + ledger.audit.length + ' 次，保留修改前记录）</summary>' + (ledger.audit.length ? ledger.audit.map(a => '<div><b>' + esc(a.at) + ' · ' + esc(a.reason) + '</b>' + a.changes.map(c => '<p>原：' + esc(hdTradeDescribe(c.before)) + '<br>新：' + esc(hdTradeDescribe(c.after)) + '</p>').join('') + '</div>').join('') : '<p class="hint">还没有人工修改记录。</p>') + '</details></section>';
}
function hdTradePaste(r, text, targetId) {
  const d = hdTradeDraft(r), cells = []; let row = [], cell = '', quoted = false;
  const input = text.replace(/\r\n?/g, '\n');
  for (let i = 0; i < input.length; i++) {
    const ch = input[i];
    if (ch === '"' && (!cell || quoted)) { if (quoted && input[i + 1] === '"') { cell += '"'; i++; } else quoted = !quoted; }
    else if ((ch === '\t' || ch === '\n') && !quoted) { row.push(cell); cell = ''; if (ch === '\n') { cells.push(row); row = []; } }
    else cell += ch;
  }
  row.push(cell); cells.push(row);
  const rows = cells.filter(c => c.some(x => x.trim()));
  if (rows.length && /日期|date/i.test(rows[0][0])) rows.shift();
  if (quoted || !rows.length || rows.length > 500 || rows.some(c => c.length < 4 || c.length > 5)) { d.errors = ['粘贴内容需为 4～5 列：日期、买卖方向、价格、股数、备注；每次最多 500 行，请检查是否复制了完整区域。']; return; }
  const parsed = rows.map(c => {
    const date = c[0].trim().replace(/[/.]/g, '-').replace(/^(\d{4})-(\d{1,2})-(\d{1,2})$/, (_, y, m, day) => y + '-' + m.padStart(2, '0') + '-' + day.padStart(2, '0'));
    const sideText = c[1].trim().toLowerCase();
    return { date: date, side: ['买入', '买', 'buy', '证券买入'].includes(sideText) ? 'buy' : ['卖出', '卖', 'sell', '证券卖出'].includes(sideText) ? 'sell' : sideText, price: c[2].trim().replace(/[,，]/g, ''), shares: c[3].trim().replace(/[,，]/g, ''), note: (c[4] || '').trim() };
  });
  const target = d.entries.find(t => t.id === targetId);
  if (target && !hdTradeLedger(r).entries.some(t => t.id === target.id)) d.entries = d.entries.filter(t => t.id !== target.id);
  parsed.forEach(values => Object.assign(hdTradeAdd(r), values));
  d.paste = ''; d.pasteOpen = false; d.preview = null; d.errors = [];
}
function handleHdLedgerAction(action, el) {
  const r = hdTradeStock(el.dataset.hd);
  if (!r) return;
  if (action === 'hd-ledger-archive') { state.hdArchiveId = r.id; renderView(); return; }
  if (state.hdForm) { toast('请先完成当前成本修正', '保存或取消成本修正后，再维护成交明细。', 'warn'); return; }
  const d = hdTradeDraft(r), id = el.dataset.trade;
  const t = d.entries.find(t => t.id === id);
  if (action === 'hd-ledger-add') hdTradeAdd(r);
  else if (action === 'hd-ledger-edit' && t) { if (!d.editing.includes(id)) d.editing.push(id); }
  else if (action === 'hd-ledger-void' && t) { t.status = 'void'; d.preview = null; }
  else if (action === 'hd-ledger-undo' && t) { d.entries[d.entries.indexOf(t)] = clone(hdTradeLedger(r).entries.find(o => o.id === id)); d.editing = d.editing.filter(x => x !== id); }
  else if (action === 'hd-ledger-remove') d.entries = d.entries.filter(t => t.id !== id);
  else if (action === 'hd-ledger-paste-open') d.pasteOpen = !d.pasteOpen;
  else if (action === 'hd-ledger-paste') hdTradePaste(r, d.paste);
  else if (action === 'hd-ledger-preview') hdTradePreview(r, d);
  else if (action === 'hd-ledger-back') { d.preview = null; d.errors = []; d.duplicatesOk = false; }
  else if (action === 'hd-ledger-discard') { if (d.discardAsk) delete state.hdTradeDrafts[r.id]; else d.discardAsk = true; }
  else if (action === 'hd-ledger-keep') d.discardAsk = false;
  else if (action === 'hd-ledger-save' && hdTradeCommit(r, d)) {
    if (d.quick) { state.hdView = hdData().length ? d.quickView : 'exited'; hdQuickDone(r, '全部成交已保存，修改前记录已保留', r.shares ? 'reduce' : 'exit'); return; }
    toast('已保存全部变更', '持股、均价、盈亏及账户数字已重算，修改前的记录保留在「修改留痕」。', 'ok');
  }
  renderView(); syncHdHash();
  if (action === 'hd-ledger-add' || action === 'hd-ledger-edit') {
    const inputs = document.querySelectorAll('.hd-trade-table [data-field="date"]');
    if (inputs.length) inputs[inputs.length - 1].focus({ preventScroll: true });
  }
}

function hdOpsTab(r) {
  const open = state.hdForm && String(state.hdForm.id) === String(r.id);
  const preview = state.hdTradeDrafts[r.id] && state.hdTradeDrafts[r.id].preview;
  return '<div class="hd-ops-bar">' +
    [['add', '记买入 / 加仓'], ['reduce', '记卖出 / 减仓'], ['exit', '记全部卖出'], ['cost', '修正成本']].map(([kind, label]) => '<button class="btn sm" data-action="hd-op" data-hd="' + r.id + '" data-kind="' + kind + '"' + (open || preview ? ' disabled' : '') + '>' + label + '</button>').join('') +
    '<span class="hint">快捷填入下方明细表；可继续追加多笔，一次确认。</span></div>' +
    (open ? (state.hdForm.confirm && state.hdForm.values ? hdConfirmHtml(r, state.hdForm.kind, state.hdForm.values) : hdFormHtml(r, state.hdForm.kind)) : hdTradeTableHtml(r)) +
    '<details class="hd-trade-audit"><summary>历史系统提醒（不作为成交参与重算）</summary><div class="timeline">' + r.trades.filter(t => t.side === 'sys').map(t => '<div class="tl-item"><div class="tl-head">' + esc(t.date) + '</div><div class="tl-body">' + esc(t.note) + '</div></div>').join('') + '</div></details>';
}

function hdRiskTab(r) {
  const reds = hdReds(r);
  return '<div class="hd-risk-table"><div class="hd-risk-head"><span>红线</span><span>现在</span><span>阈值</span><span>说人话</span></div>' +
    reds.map((x) => '<div class="hd-risk-row"><span class="hd-risk-name"><span class="state ' + x.st + '"></span>' + esc(x.name) + '<em>' + esc(x.code) + '</em></span>' +
      '<span class="mono">' + esc(x.cur) + '</span><span class="dim">' + esc(x.limit) + '</span><span>' + esc(x.plain) + '</span></div>').join('') + '</div>' +
    '<dl class="kv" style="margin-top:14px">' +
      '<dt>止盈与仓位计划</dt><dd>止损 ' + r.stop.toFixed(2) + ' · 止盈 ' + r.tp.toFixed(2) + ' · 目标仓位 ' + r.targetPct + '% · 防御期建议 ' + r.suggestPct + '%</dd>' +
      '<dt>移动止盈档位</dt><dd>' + (r.trail ? esc(r.trail.stage) + ' <span class="hint">' + esc(r.trail.next) + '</span>' : '<span class="dim">这笔没有设移动止盈（短线持有）</span>') + '</dd>' +
      '<dt>组合口径</dt><dd>当前总仓位 ' + hdTotalShare().toFixed(1) + '% · C2 上限 ' + HD_CAP.total + '% · 防御期软上限 ' + HD_CAP.softCap + '%（沪指 ' + state.hdAccount.index.toFixed(0) + '）</dd>' +
      '<dt>最近告警</dt><dd>' + (r.alerts ? r.alerts + ' 条 · <button class="btn link xs" data-nav="#/alerts?code=' + r.code + '">去告警日志 ' + icon('arrow', 'sm') + '</button>' : '<span class="dim">暂无告警</span>') + '</dd>' +
      (r.rules.length ? '<dt>依据的规则</dt><dd>' + r.rules.map((x) => x.id
        ? '<button class="btn link xs" data-nav="#/system/rules?bucket=all&id=' + x.id + '">' + esc(x.name) + ' ' + esc(x.id) + ' ' + icon('arrow', 'sm') + '</button>'
        : '<span class="dim">' + esc(x.name) + '（这条是后端口径，没有单独编号）</span>').join(' · ') + '</dd>' : '') +
    '</dl>' +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>四条红线的唯一裁决在后端（<code>GET /api/red_line_check</code>），页面上的颜色只是提前告诉你哪条快碰线了。左侧代号 C1 / C2 / C3 / K139 是系统内部编号，日常不用记。</div></div>';
}

function hdKlineHtml(r) {
  return '<section class="hd-kline-panel" id="hd-kline-panel" aria-label="K线与关键价位">' +
    '<div class="hd-kline-head"><b>K线对照</b><span class="hint">切换标的时同步更新</span></div>' +
    (r.price == null ? '<div class="cp-scene-empty">暂未取到行情，不绘制K线和均线。请刷新行情，或通过上方链接查看真实盘面。</div>' :
      candKlineHtml({ stock_code: r.code, stock_name: r.name, trade_date: r.entry, trend: hdTrend(r) }, '建仓日', true)) +
    '<dl class="hd-kline-prices">' + [['现价', r.price], ['成本', r.cost], ['止损', r.stop], ['止盈', r.tp]].map(([label, value]) =>
      '<div><dt>' + label + '</dt><dd class="mono">' + (value == null ? '无行情' : value.toFixed(2)) + '</dd></div>').join('') + '</dl>' +
    '<div class="hd-kline-verdict">' + hdVerdictPill(hdVerdict(r)) + '<p>' + esc(hdConcl(r)) + '</p></div>' +
  '</section>';
}

function hdDetailHtml(r) {
  const tabs = [['concl', '现在怎么办'], ['basis', '判断依据'], ['ops', '买卖记录'], ['risk', '风控与计划']];
  const body = state.hdTab === 'basis' ? hdBasisTab(r)
    : state.hdTab === 'ops' ? hdOpsTab(r)
    : state.hdTab === 'risk' ? hdRiskTab(r) : hdConclTab(r);
  return '<div class="card">' +
    '<div class="detail-head">' +
      '<div style="min-width:0">' +
        '<div class="detail-title">' + esc(r.name) + ' <span class="mono dim">' + r.code + '</span> ' + tag(r.source, 'outline') + '</div>' +
        '<div class="detail-sub">持仓 #' + r.id + ' · 建仓 ' + esc(r.entry) + ' · ' + r.shares + ' 股 · 成本 ' + r.cost.toFixed(2) + '</div>' +
        '<div class="detail-tags">' + hdVerdictPill(hdVerdict(r)) + ' ' +
          (hdPnl(r) == null ? tag('无行情', 'mute') : tag(hdMoney(hdPnl(r)) + ' 元', hdPnl(r) >= 0 ? 'red' : 'green')) +
          (hdRedDot(r) === 'err' ? tag('踩线', 'red') : hdRedDot(r) === 'warn' ? tag('预警', 'gold') : '') + '</div>' +
      '</div>' +
      '<div class="spacer"></div>' +
      '<div class="cp-acts">' +
        '<button class="btn primary sm" data-action="hd-manual" data-hd="' + r.id + '">' + icon('plus', 'sm') + '手动记买卖</button>' +
        '<button class="btn sm" data-action="hd-kline" data-hd="' + r.id + '" aria-expanded="' + state.hdKlineOpen + '"' + (state.hdKlineOpen ? ' aria-controls="hd-kline-panel"' : '') + '>' + icon('chart', 'sm') + (state.hdKlineOpen ? '收起K线' : '看K线 · 同屏对照') + '</button>' +
        '<div class="cp-ext">' + quoteUrls(r.code).map((q) => '<a class="btn link xs" href="' + q.url + '" target="_blank" rel="noopener noreferrer">' + esc(q.name) + ' ' + icon('external', 'sm') + '</a>').join('') + '</div>' +
      '</div>' +
    '</div>' +
    '<div class="hd-detail-content' + (state.hdKlineOpen ? ' with-kline' : '') + '">' +
    (state.hdKlineOpen ? hdKlineHtml(r) : '') + '<div class="hd-context">' +
    '<div class="detail-tabs">' + tabs.map((t) =>
      '<button class="detail-tab ' + (state.hdTab === t[0] ? 'active' : '') + '" data-action="hd-tab" data-tab="' + t[0] + '">' + t[1] +
      (t[0] === 'ops' ? ' ' + tag(String(r.trades.length), 'mute') : '') + '</button>').join('') + '</div>' +
    '<div class="cp-tab-body">' + (r.historyEdited ? '<div class="hd-warns">成交已更新，以下原 AI 判断与价位计划未自动改写；请核对后重新研判。</div>' : '') + body + '</div></div></div>' +
  '</div>';
}

function hdRowHtml(r) {
  const v = hdVerdict(r);
  const active = String(state.hdId) === String(r.id);
  const quick = v === 'exit' ? 'exit' : v === 'reduce' ? 'reduce' : null;
  const openForm = state.hdForm && String(state.hdForm.id) === String(r.id);
  const acts = quick && !openForm
    ? '<span class="rq-acts">' + rqBtn('hd-row-op', 'hd', r.id, v === 'exit' ? '记清仓' : '记减仓', true) + '</span>'
    : '';
  const reds = hdReds(r).filter((x) => x.st === 'bad' || x.st === 'todo');
  return '<div class="cp-row hd-row' + (active ? ' active' : '') + '" role="button" tabindex="0" data-action="hd-select" data-hd="' + r.id + '">' +
    '<div class="cp-row-top">' +
      '<span class="hold-dot ' + hdRedDot(r) + '"></span>' +
      '<span class="cp-name">' + esc(r.name) + ' <span class="mono dim">' + r.code + '</span></span>' +
      '<span class="spacer"></span>' +
      '<span class="mono ' + hdPnlCls(hdPnl(r)) + '">' + (hdPnlPct(r) == null ? '—' : hdPct(hdPnlPct(r))) + '</span>' +
    '</div>' +
    '<div class="cp-row-reason">' + esc(hdConcl(r)) + '</div>' +
    '<div class="hd-row-nums">' +
      '<span>现价 <b class="mono">' + (r.price == null ? '—' : r.price.toFixed(2)) + '</b></span>' +
      '<span>成本 <b class="mono">' + r.cost.toFixed(2) + '</b></span>' +
      '<span>止损 <b class="mono ' + (hdStopDist(r) != null && hdStopDist(r) < 3 ? 'wo-down' : '') + '">' + r.stop.toFixed(2) + (hdStopDist(r) == null ? '' : '（距 ' + hdStopDist(r).toFixed(1) + '%）') + '</b></span>' +
      '<span>占比 <b class="mono">' + hdShare(r).toFixed(1) + '%</b></span>' +
    '</div>' +
    (reds.length ? '<div class="hd-row-reds">' + reds.map((x) => tag(x.name + ' · ' + (x.st === 'bad' ? '已踩线' : '预警'), x.st === 'bad' ? 'red' : 'gold')).join(' ') + '</div>' : '') +
    '<div class="cp-row-foot">' +
      '<span class="mono dim">' + r.shares + ' 股</span>' +
      '<span class="dim">' + hdMoney(hdMv(r)) + ' 元</span>' +
      (r.alerts ? tag(r.alerts + ' 条告警', 'outline') : '') +
      '<span class="spacer"></span>' + hdVerdictPill(v) + acts +
    '</div>' +
  '</div>';
}

/* ---------- 页面 ---------- */
const HD_VIEWS = [['todo', '要我处理'], ['all', '全部持仓'], ['exited', '已离场'], ['check', '数据待核对']];

function hdStats() {
  const todo = hdTodo();
  const watch = hdData().filter((r) => hdVerdict(r) === 'watch').length;
  const share = hdTotalShare();
  const today = hdTodayPnl();
  return [
    { label: '总资产', value: (state.hdAccount.total / 10000).toFixed(1) + ' 万', sub: '现金 ' + (hdCash() / 10000).toFixed(1) + ' 万 · 市值 ' + (hdTotalMv() / 10000).toFixed(1) + ' 万', tone: '' },
    { label: '总仓位', value: share.toFixed(1) + '%', sub: 'C2 上限 60% · 防御期软上限 20%', tone: share > HD_CAP.total ? 'err' : share > HD_CAP.softCap ? 'warn' : 'ok' },
    { label: '今日盈亏', value: (today >= 0 ? '+' : '-') + hdMoney(Math.abs(Math.round(today))), sub: '浮盈合计 ' + hdMoney(hdData().reduce((s, r) => s + (hdPnl(r) || 0), 0)) + ' 元', tone: today > 0 ? 'up' : today < 0 ? 'down' : '' },
    { label: '等你处理', value: todo.length + ' 只', sub: watch ? '另有 ' + watch + ' 只到价待确认' : '都是「继续拿」', tone: todo.length ? 'warn' : 'ok' }
  ];
}

/* 持仓的计数条：措辞跟着队列语义走，不复用「裁决/采纳/驳回」那套 */
function hdRqBar(n) {
  return '<div class="rq-bar">' + (n
    ? '<b>等你处理 ' + n + ' 只</b><span class="dim">行上直接点「记清仓 / 记减仓」，记完自动跳到下一只，不用进详情；上下键换行</span>'
    : '<span class="dim">现在没有要你动手的持仓，剩下的是「继续拿」和「到价了」</span>') + '</div>';
}

function hdSentinelHtml() {
  return '<div class="hd-sentinel">' +
    '<div class="hd-sentinel-head">' + icon('shield', 'sm') + '<b>账户风险提醒</b>' +
      '<span class="hint">帮你看看：股票买得是否太满，资金是否太集中</span>' +
      '<span class="spacer"></span>' +
      '<button class="btn xs" data-action="hd-sentinel">' + icon('rotate', 'sm') + '重新检查</button>' +
      '<button class="btn link xs" data-nav="#/alerts">查看提醒记录 ' + icon('arrow', 'sm') + '</button></div>' +
    '<div class="hd-sentinel-intro">上面看单只股票，这里汇总整个账户需要注意的地方。建议先看止损提醒，再看总仓位和单只股票占比；只做提醒，不会替你买卖。缺少行情的持仓，请先核对数据。</div>' +
    hdSentinelItems().map((s) => '<div class="hd-sentinel-item"><span class="state ' + s.level + '"></span>' +
      '<div><b>' + esc(s.title) + '</b><div class="hd-sentinel-body">' + esc(s.body) + '</div>' +
      '<span class="hint dim">提醒时间 ' + esc(s.at) + '</span></div>' +
      '<span class="spacer"></span><button class="btn xs" data-nav="' + s.nav + '">' + esc(s.navLabel) + ' ' + icon('arrow', 'sm') + '</button></div>').join('') +
  '</div>';
}

function hdExitedHtml() {
  const selected = state.hdArchiveId != null ? hdTradeStock(state.hdArchiveId) : null;
  return '<div class="card">' +
    '<div class="card-title"><h3>已离场（' + state.exited.length + '）</h3><span class="hint">记录成交后自动归档到这里；盈亏是已实现口径</span></div>' +
    '<div class="hd-exited">' + state.exited.map((x) =>
      '<div class="hd-exited-row"><span class="cp-name">' + esc(x.name) + ' <span class="mono dim">' + esc(x.code) + '</span></span>' +
      '<span class="mono dim">' + esc(x.entry) + ' → ' + esc(x.exit) + '</span>' +
      '<span class="mono">' + x.shares + ' 股 @ ' + x.out.toFixed(2) + '</span>' +
      '<span class="mono ' + hdPnlCls(x.realized == null ? x.pnl : x.realized) + '">' + (x.realized == null ? hdPct(x.pnl, 1) : '累计已实现 ' + hdMoney(Number(x.realized.toFixed(2))) + ' 元') + '</span>' +
      '<button class="btn sm" data-action="hd-ledger-archive" data-hd="' + (x.row ? x.row.id : x.id) + '">维护买卖明细</button>' +
      '<span class="dim">' + esc(x.note) + '</span>' +
      '<span class="spacer"></span>' +
      (x.reviewId ? '<button class="btn link xs" data-nav="#/reviews?id=' + x.reviewId + '">看这笔复盘 ' + icon('arrow', 'sm') + '</button>'
        : '<button class="btn link xs" data-nav="#/reviews">复盘队列 ' + icon('arrow', 'sm') + '</button>') +
      '</div>').join('') + '</div>' +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>已离场也能补录、修改或作废成交。先预览持股与盈亏变化，再确认；若恢复持股，会重新进入持仓监控。原复盘保留，修改成交不会自动改写已有复盘。</div></div>' +
    (selected && !hdById(selected.id) ? '<div class="hd-archive-editor">' + hdTradeTableHtml(selected) + '</div>' : '') +
  '</div>';
}

/* 抽屉里的三个录入口子：对齐生产 AddHoldingModal / OcrModal / BaselineModal */
function hdTrend(r) {
  const n = 12, from = r.cost, to = hdPrice(r), seed = code5(r.code);
  return Array.from({ length: n }, (_, i) =>
    Math.round((from + (to - from) * (i / (n - 1)) + Math.sin(i * 1.7 + seed) * from * 0.014) * 100) / 100);
}

function hdNewFormHtml(v, warns) {
  const d = Object.assign({ code: '', name: '', date: '2026-11-16', price: '', shares: '', plan: '', stop: '', tp: '', target: '', note: '' }, v || {});
  const f = (label, id, input) => '<label class="hd-field"><span>' + label + '</span>' + input + '</label>';
  const num = (label, id, val, attrs) => f(label, id, '<input class="input" id="' + id + '" type="number" ' + (attrs || '') + ' value="' + esc(String(val)) + '">');
  return '<div class="hd-form in-drawer">' +
    '<div class="hd-form-title">录入人工建仓 <span class="hint">你已经成交的结果，系统不下单</span></div>' +
    '<div class="hd-form-grid">' +
      f('证券代码 *', 'hd-n-code', '<input class="input mono" id="hd-n-code" maxlength="6" placeholder="603501" value="' + esc(d.code) + '">') +
      f('名称 *', 'hd-n-name', '<input class="input" id="hd-n-name" placeholder="韦尔股份" value="' + esc(d.name) + '">') +
      f('建仓日期 *', 'hd-n-date', '<input class="input" id="hd-n-date" type="date" value="' + esc(d.date) + '">') +
      num('成交价 *', 'hd-n-price', d.price, 'step="0.01" placeholder="118.60"') +
      num('股数 *（100 整数倍）', 'hd-n-shares', d.shares, 'step="100" min="100" placeholder="300"') +
      f('关联建仓计划号', 'hd-n-plan', '<input class="input mono" id="hd-n-plan" placeholder="812，可留空" value="' + esc(d.plan) + '">') +
      num('止损位（留空按成本 ×0.92）', 'hd-n-stop', d.stop, 'step="0.01"') +
      num('止盈位（留空按 +15% 起档）', 'hd-n-tp', d.tp, 'step="0.01"') +
      num('目标仓位 %', 'hd-n-target', d.target, 'step="1" placeholder="10"') +
      f('备注', 'hd-n-note', '<input class="input" id="hd-n-note" placeholder="为什么建这一笔" value="' + esc(d.note) + '">') +
    '</div>' +
    (warns && warns.length ? '<div class="hd-warns">' + warns.map((w) =>
      '<div class="hd-warn">' + icon('alert', 'sm') + esc(w) + '</div>').join('') +
      '<div class="hint">以上是风险提示，不是拦截；确认后照样记录，但会写进留痕。</div></div>' : '') +
    '<div class="hd-form-acts">' +
      '<button class="btn sm" data-action="close-drawer">取消</button><span class="spacer"></span>' +
      (warns && warns.length
        ? '<button class="btn sm" data-action="hd-new-check">返回改数字</button><button class="btn danger sm" data-action="hd-new-force">仍然记录这一笔</button>'
        : '<button class="btn primary sm" data-action="hd-new-save">校验并记录</button>') +
    '</div>' +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>记录后立刻按知识库规则算出止损位、移动止盈档位和单票占比；口径与「立即刷新监控」用的是同一套后端规则，不在前端另写一份。</div></div>' +
  '</div>';
}

function hdOcrFormHtml() {
  if (!state.hdOcrDone) {
    return '<div class="hd-form in-drawer">' +
      '<div class="hd-form-title">OCR 截图建仓 <span class="hint">入口由后端开关控制</span></div>' +
      '<label class="hd-field wide"><span>持仓截图</span><input class="input" id="hd-o-file" type="file" accept="image/*"></label>' +
      '<div class="hd-warns"><div class="hd-warn">' + icon('info', 'sm') + '识别服务（ocrStatus.enabled）没配好时，这个入口整块是灰的；正式端会在打开抽屉时先查一次状态。</div></div>' +
      '<div class="hd-form-acts"><button class="btn sm" data-action="close-drawer">取消</button><span class="spacer"></span>' +
        '<button class="btn primary sm" data-action="hd-ocr-run">模拟识别完成</button></div>' +
      '<div class="cap-note" style="margin-top:12px">' + icon('alert', 'sm') + '<div>识别出来的数字<b>不直接写库</b>。必须在下面这一屏逐行核对，尤其是成本和股数——OCR 把 34.20 认成 31.20 是常事。</div></div>' +
    '</div>';
  }
  return '<div class="hd-form in-drawer">' +
    '<div class="hd-form-title">识别结果核对 <span class="hint">2 笔 · 逐行确认后才写入</span></div>' +
    '<div class="hd-ocr-rows">' + state.hdOcrRows.map((o, i) =>
      '<div class="hd-ocr-row">' +
        '<span class="cp-name">' + esc(o.name) + ' <span class="mono dim">' + o.code + '</span></span>' +
        '<label class="hd-field"><span>成交价</span><input class="input mono" id="hd-o-p-' + i + '" type="number" step="0.01" value="' + o.price.toFixed(2) + '"></label>' +
        '<label class="hd-field"><span>股数</span><input class="input mono" id="hd-o-s-' + i + '" type="number" step="100" value="' + o.shares + '"></label>' +
        '<span class="hint">' + esc(o.note) + '</span>' +
      '</div>').join('') + '</div>' +
    '<div class="hd-form-acts"><button class="btn sm" data-action="close-drawer">取消</button><span class="spacer"></span>' +
      '<button class="btn sm" data-action="hd-ocr-run">重新识别</button>' +
      '<button class="btn primary sm" data-action="hd-ocr-save">核对无误，录入 ' + state.hdOcrRows.length + ' 笔</button></div>' +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>同一只票同一天重复录入会被自动去重，只保留一条「当前有效」，其余标成「重复录入（已自动忽略）」——在详情「买卖记录」的建仓笔次表里能看到。</div></div>' +
  '</div>';
}

function hdBaselineFormHtml(v) {
  const d = Object.assign({ total: state.hdAccount.total, cash: state.hdAccount.cash }, v || {});
  return '<div class="hd-form in-drawer">' +
    '<div class="hd-form-title">账户基线 <span class="hint">总资产和现金决定总仓位口径</span></div>' +
    '<div class="hd-form-grid">' +
      '<label class="hd-field"><span>总资产（元）*</span><input class="input mono" id="hd-b-total" type="number" step="100" value="' + d.total + '"></label>' +
      '<label class="hd-field"><span>可用现金（元）*</span><input class="input mono" id="hd-b-cash" type="number" step="100" value="' + d.cash + '"></label>' +
    '</div>' +
    '<dl class="kv" style="margin-top:12px">' +
      '<dt>当前持仓市值</dt><dd class="mono">' + hdMoney(hdTotalMv()) + ' 元</dd>' +
      '<dt>当前总仓位</dt><dd class="mono">' + hdTotalShare().toFixed(1) + '%　<span class="hint">C2 上限 ' + HD_CAP.total + '%</span></dd>' +
      '<dt>沪指</dt><dd class="mono">' + state.hdAccount.index.toFixed(2) + '　<span class="hint">' +
        (state.hdAccount.index < HD_CAP.indexBar ? '低于 ' + HD_CAP.indexBar + '，防御期软上限 ' + HD_CAP.softCap + '%' : '高于 ' + HD_CAP.indexBar + '，非防御期') + '</span></dd>' +
    '</dl>' +
    '<div class="hd-form-acts"><button class="btn sm" data-action="close-drawer">取消</button><span class="spacer"></span>' +
      '<button class="btn primary sm" data-action="hd-baseline-save">保存并重算仓位</button></div>' +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') + '<div>总资产改小，单票占比和总仓位会立刻顶上来；这一屏下面的数字保存后会全部重算，包括左侧每只票的结论。</div></div>' +
  '</div>';
}

function hdReadNew() {
  const g = (id) => { const el = $('#' + id); return el ? String(el.value).trim() : ''; };
  const v = { code: g('hd-n-code'), name: g('hd-n-name'), date: g('hd-n-date'), price: g('hd-n-price'), shares: g('hd-n-shares'), plan: g('hd-n-plan'), stop: g('hd-n-stop'), tp: g('hd-n-tp'), target: g('hd-n-target'), note: g('hd-n-note') };
  const err = (t, b, focus) => { toast(t, b, 'warn'); if (focus) { const el = $('#' + focus); if (el) el.focus(); } return null; };
  if (!/^\d{6}$/.test(v.code)) return err('代码要 6 位数字', '例如 603501。带市场的后缀在这里不用填，前缀由系统按代码段判断。', 'hd-n-code');
  if (!v.name) return err('名称要填', '列表和结论都用名称，光有代码看不下去。', 'hd-n-name');
  const price = parseFloat(v.price), shares = parseInt(v.shares, 10);
  if (!(price > 0)) return err('成交价要填正数', '按你实际成交的价格填，不是当前的市场价。', 'hd-n-price');
  if (!(shares > 0)) return err('股数要填', '一手 100 股。', 'hd-n-shares');
  if (shares % 100 !== 0) return err('股数必须是 100 的整数倍', '你填的是 ' + shares + ' 股。', 'hd-n-shares');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v.date)) return err('建仓日期格式不对', '要 YYYY-MM-DD。', 'hd-n-date');
  if (state.holdings.some((r) => r.code === v.code)) {
    return err('这只票已经在持仓里了', '同一只票再加仓位，请用详情里的「加仓」——那样才会重算加权成本。', null);
  }
  v.price_n = price; v.shares_n = shares;
  v.warns = hdNewWarns(v);
  return v;
}

function hdNewWarns(v) {
  const total = state.hdAccount.total || 1;
  const share = v.shares_n * v.price_n / total * 100;
  const rest = (hdTotalMv() + v.shares_n * v.price_n) / total * 100;
  const out = [];
  if (share > HD_CAP.gradeA) out.push('这一笔单票仓位将达 ' + share.toFixed(1) + '%，超过 A 级上限 ' + HD_CAP.gradeA + '%（硬顶 ' + HD_CAP.total + '%）');
  if (rest > HD_CAP.total) out.push('做完之后总仓位将达 ' + rest.toFixed(1) + '%，超过 C2 上限 ' + HD_CAP.total + '%');
  if (state.hdAccount.index < HD_CAP.indexBar && rest > HD_CAP.softCap) {
    out.push('现在是防御期（沪指 ' + state.hdAccount.index.toFixed(0) + ' < ' + HD_CAP.indexBar + '），总仓位软上限只有 ' + HD_CAP.softCap + '%，做完之后是 ' + rest.toFixed(1) + '%');
  }
  return out;
}

/* 只写数据、不动界面：人工建仓和 OCR 批量录入共用 */
function hdBuildRow(v) {
  const cost = v.price_n;
  const stop = v.stop ? parseFloat(v.stop) : Math.round(cost * HD_CAP.c3 * 100) / 100;
  const tp = v.tp ? parseFloat(v.tp) : Math.round(cost * 1.15 * 100) / 100;
  const id = state.holdings.concat(state.exited.map(x => x.row || x)).reduce((m, r) => Math.max(m, Number(r.id) || 0), 2000) + 1;
  const pct = v.target ? parseInt(v.target, 10) : 10;
  state.holdings.push({
    id: id, code: v.code, name: v.name, source: v.source || '人工录入', entry: v.date,
    shares: v.shares_n, cost: cost, price: cost, today: 0, dd: 0,
    stop: stop, tp: tp, targetPct: pct, suggestPct: pct,
    trail: { stage: '第一档（+15%）未到', hit: false, next: '涨到 ' + tp.toFixed(2) + ' 上移止盈' },
    plan: v.plan ? { id: Number(v.plan) || v.plan, batch: v.date } : null,
    alerts: 0, rules: [{ name: 'C3 止损红线：成本 ×0.92' }],
    concls: {}, scenes: null, decision: null, decisions: [],
    trades: [{ side: 'buy', shares: v.shares_n, price: cost, date: v.date, note: v.note || '人工录入建仓' }],
    records: [{ date: v.date, price: cost, shares: v.shares_n, created: '2026-11-16 人工录入', status: '当前有效' }]
  });
  state.hdAccount.cash = Math.max(0, hdCash() - cost * v.shares_n);
  return { id: id, stop: stop, tp: tp };
}

function hdCommitNew(v) {
  const made = hdBuildRow(v);
  state.hdId = made.id;
  state.hdView = 'all';
  state.hdTab = 'concl';
  state.hdNewPending = null;
  closeDrawer();
  renderView();
  syncHdHash();
  toast('已录入建仓', v.name + '（' + v.code + '）' + v.shares_n + ' 股 @ ' + v.price_n.toFixed(2) + '，止损位 ' + made.stop.toFixed(2) + '、第一档止盈 ' + made.tp.toFixed(2) + ' 已按规则算好。已留痕。', 'ok');
}

function hdOcrCommit() {
  const rows = state.hdOcrRows.map((o, i) => {
    const pEl = $('#hd-o-p-' + i), sEl = $('#hd-o-s-' + i);
    return { code: o.code, name: o.name, price: pEl ? parseFloat(pEl.value) : o.price, shares: sEl ? parseInt(sEl.value, 10) : o.shares, note: o.note };
  });
  const bad = rows.find((r) => !(r.price > 0) || !(r.shares > 0) || r.shares % 100 !== 0);
  if (bad) { toast('这一行数字不对', bad.name + '（' + bad.code + '）的成交价或股数没填对，股数还要是 100 的整数倍。', 'warn'); return; }
  const dup = rows.find((r) => state.holdings.some((h) => h.code === r.code));
  if (dup) { toast('这只已经在持仓里了', dup.name + '（' + dup.code + '）已有持仓，OCR 不重复建仓。这一行请删掉，或改用详情里的「加仓」。', 'warn'); return; }
  const made = rows.map((r) => hdBuildRow({
    code: r.code, name: r.name, date: '2026-11-16', price_n: r.price, shares_n: r.shares, source: 'OCR 截图',
    plan: '', stop: '', tp: '', target: '', note: 'OCR 截图建仓：' + r.note
  }));
  state.hdOcrDone = false;
  state.hdOcrRows = null;
  state.hdId = made[0].id;
  state.hdView = 'all';
  closeDrawer();
  renderView();
  syncHdHash();
  toast('OCR 结果已录入', rows.length + ' 笔写入：' + rows.map((r) => r.name).join('、') + '。识别原图与核对后的数字都留痕，可回查。', 'ok');
}

function renderHoldings() {
  hdData();
  const rows = hdVisible();
  const sel = rows.find((r) => String(r.id) === String(state.hdId)) || rows[0] || hdData()[0];
  if (sel) state.hdId = sel.id;
  const views = HD_VIEWS.map((v) => {
    const n = v[0] === 'todo' ? hdTodo().length
      : v[0] === 'all' ? hdData().length
      : v[0] === 'exited' ? state.exited.length
      : hdData().filter((r) => hdVerdict(r) === 'info').length;
    return '<button class="cp-chip ' + (state.hdView === v[0] ? 'active' : '') + '" data-action="hd-view" data-view="' + v[0] + '">' + v[1] + ' <span class="mono dim">' + n + '</span></button>';
  }).join('');

  const head = '<div class="page-head"><div>' +
      '<div class="page-title">持仓监控</div>' +
      '<div class="page-sub">手上的票现在该怎么办：结论、动手价位、就地记录成交。行情约 60 秒缓存，红线约 10 分钟一轮。</div>' +
    '</div>' +
    '<div class="page-actions">' +
      '<button class="btn sm" data-action="hd-refresh">' + icon('rotate', 'sm') + '立即刷新监控</button>' +
      '<button class="btn sm" data-action="hd-add">' + icon('plus', 'sm') + '录入人工建仓</button>' +
      '<button class="btn sm" data-action="hd-ocr">' + icon('download', 'sm') + 'OCR 截图建仓</button>' +
      '<button class="btn sm" data-action="hd-baseline">' + icon('sliders', 'sm') + '账户基线</button>' +
    '</div></div>';

  const list = state.hdView === 'exited'
    ? hdExitedHtml()
    : '<div class="cp-layout' + (state.hdKlineOpen ? ' hd-compare' : '') + '">' +
        '<div class="card cp-list-card">' + hdRqBar(hdTodo().length) +
          '<div class="cp-list" id="hd-list">' + (rows.length ? rows.map(hdRowHtml).join('') : '<div class="wo-empty" style="padding:14px">这个视图下没有持仓。</div>') + '</div>' +
          '<div class="hd-list-foot"><span class="hint">共 ' + rows.length + ' 只 · 按「要不要动手」排序，同档按单票占比从高到低</span>' +
            '<span class="spacer"></span><span class="hint dim">行情 ' + esc(state.hdAccount.quoteTime) + '</span>' +
            '<button class="btn link xs" data-action="hd-refresh">刷新行情</button></div>' +
        '</div>' +
        '<div class="cp-detail" id="hd-detail">' + (sel ? hdDetailHtml(sel) : '<div class="card"><div class="wo-empty" style="padding:20px">没有可选持仓。</div></div>') + '</div>' +
      '</div>' + hdSentinelHtml();

  return head +
    '<div class="cp-toolbar"><div class="cp-chips">' + views + '</div>' +
      '<span class="hint">操作都在行上和详情里就地完成；这一页不做买卖，只记录你已经成交的结果。</span>' +
      '<span class="spacer"></span><button class="btn link sm" data-nav="#/market-intel?board=volume">看今天的结构与板块量能 ' + icon('arrow', 'sm') + '</button></div>' +
    '<div class="metric-strip q4" style="margin-bottom:14px">' + hdStats().map((s) =>
      '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div><div class="metric-value ' + s.tone + '">' + esc(s.value) + '</div><div class="metric-sub">' + esc(s.sub) + '</div></div>').join('') + '</div>' +
    list +
    '<div class="cap-note" style="margin-top:14px">' + icon('info') + '<div>闭环：候选池建仓 → 这里盯与记 → 清仓自动进复盘 → 复盘出的建议进闭环队列 → 通过后变成经验与规则。红线口径全部来自后端，页面只负责让你先看见。</div></div>';
}

function syncHdHash() {
  if (state.route !== '#/holdings') return;
  let next = '#/holdings?view=' + state.hdView + '&id=' + state.hdId;
  if (state.hdTab !== 'concl') next += '&tab=' + state.hdTab;
  if (location.hash !== next) history.replaceState(null, '', next);
}
/* 就地记录之后的收尾：结论没变就留在这一只，变了才跳下一只要处理的 */
function hdQuickDone(r, msg, kind) {
  const rest = hdTodo();
  const still = rest.some((x) => String(x.id) === String(r.id));
  const next = still ? null : (rest[0] || null);
  if (next) {
    state.hdId = Number(next.id);
    state.hdTab = 'concl';
  }
  renderView();
  if (next) {
    const el = document.querySelector('.hd-row[data-hd="' + next.id + '"]');
    if (el) el.scrollIntoView({ block: 'nearest' });
  }
  const tail = still
    ? ' · 这一只的结论还是「' + HD_VERDICT[hdVerdict(r)].label + '」，没处理完就留在这里，接着记' + (kind === 'cost' ? '减仓' : '对应的成交')
    : next
      ? ' · 下一只要处理：' + next.name + '（' + HD_VERDICT[hdVerdict(next)].label + '）'
      : (kind === 'exit' ? ' · 现在没有要你动手的持仓了，剩下的是「继续拿」和「到价了」' : ' · 要处理的都做完了');
  toast(kind === 'exit' ? '已记录清仓' : kind === 'cost' ? '成本已修正' : '已记录成交', msg + tail, 'ok');
  syncHdHash();
}

/* ---------- 持仓监控：动作分派 ---------- */
function hdOpenForm(id, kind, quick) {
  const r = hdById(id);
  if (!r) { toast('这只已离场', '请在「已离场」中维护历史成交。', 'info'); return; }
  if (kind !== 'cost') {
    if (state.hdForm) { toast('请先完成当前成本修正', '保存或取消后再记买卖。', 'warn'); return; }
    const d = hdTradeDraft(r);
    if (quick) { d.quick = true; d.quickView = state.hdView; }
    if (!d.preview && kind === 'exit') {
      const entries = d.entries.map(t => t.side === 'adjust' ? t : Object.assign({}, t, { price: Number(t.price), shares: Number(t.shares), order: Number(t.order) }));
      const replay = hdTradeReplay(entries);
      if (entries.some(t => t.status !== 'void' && t.side !== 'adjust' && (!hdTradeDate(t.date) || !['buy', 'sell'].includes(t.side) || !(t.price > 0) || !Number.isSafeInteger(t.shares) || t.shares <= 0)) || replay.errors.length || !replay.shares) { toast('请先核对已有明细', '补齐或移除未填完整的行，再按草稿剩余股数记全部卖出。', 'warn'); return; }
      hdTradeAdd(r, kind).shares = replay.shares;
    } else if (!d.preview) hdTradeAdd(r, kind);
    state.hdId = r.id; state.hdTab = 'ops'; renderView(); syncHdHash();
    return;
  }
  if (state.hdTradeDrafts[r.id]) { toast('请先处理成交草稿', '保存或放弃草稿后再修正成本，避免两份改动互相覆盖。', 'warn'); return; }
  const same = state.hdForm && String(state.hdForm.id) === String(r.id) && state.hdForm.kind === kind;
  state.hdId = Number(r.id);
  state.hdTab = 'ops';
  state.hdForm = same ? null : { id: Number(r.id), kind: kind, quick: !!quick, confirm: false, values: null };
  renderView();
  syncHdHash();
  if (!same) {
    const f = $('#hd-f-shares') || $('#hd-f-price') || $('#hd-f-cost');
    if (f) f.focus();
  }
}

/* 「记录成交」按钮按结论决定先给你哪一个口子 */
function hdEnterKind(r) {
  const v = hdVerdict(r);
  if (v === 'exit') return 'exit';
  if (v === 'reduce' || v === 'watch') return 'reduce';
  if (v === 'info') return 'cost';
  return 'add';
}

function handleHdAction(action, el) {
  if (action.indexOf('hd-ledger-') === 0) { handleHdLedgerAction(action, el); return; }
  if (action === 'hd-form-keep') return;
  const kind = el.dataset.kind;
  const r = el.dataset.hd ? hdById(el.dataset.hd) : null;

  if (action === 'hd-view') {
    state.hdView = el.dataset.view;
    state.hdForm = null;
    renderView();
    syncHdHash();
  } else if (action === 'hd-select') {
    if (!r) return;
    state.hdId = Number(r.id);
    renderView();
    syncHdHash();
  } else if (action === 'hd-tab' || action === 'hd-jump-tab') {
    const tab = el.dataset.tab;
    if (['concl', 'basis', 'ops', 'risk'].indexOf(tab) < 0) return;
    state.hdTab = tab;
    renderView();
    syncHdHash();
    if (action === 'hd-jump-tab') {
      const row = r || hdById(state.hdId);
      if (row) hdOpenForm(row.id, hdEnterKind(row));
    }
  } else if (action === 'hd-hist-toggle') {
    state.hdHistOpen = !state.hdHistOpen;
    renderView();
  } else if (action === 'hd-kline') {
    if (!r) return;
    state.hdKlineOpen = !state.hdKlineOpen;
    renderView();
    $('#hd-detail [data-action="hd-kline"]').focus({ preventScroll: true });
    $('#hd-detail').scrollIntoView({ block: 'start' });
  } else if (action === 'hd-manual') {
    state.hdTab = 'ops';
    renderView();
    syncHdHash();
    $('#hd-detail .hd-ops-bar').scrollIntoView({ block: 'nearest' });
  } else if (action === 'hd-refresh') {
    state.hdAccount.quoteTime = '2026-11-16 15:12:30';
    renderView();
    toast('监控已跑完一轮', 'monitor_all 已对 ' + state.holdings.length + ' 只持仓逐个取行情、重算红线。行情约 60 秒缓存，红线约 10 分钟一轮；数字没变就不写库，只更新「最后更新」时间。', 'info');
  } else if (action === 'hd-sentinel') {
    const items = hdSentinelItems();
    renderView();
    const count = items.filter((x) => x.level !== 'done').length;
    toast('账户检查已更新', count ? '按当前页面数据，有 ' + count + ' 类情况需要留意，可查看对应的持仓详情。这里只更新提示，不会自动买卖。' : '按当前页面数据，暂未发现超限提醒。可继续按原计划关注。', items.some((x) => x.level === 'bad') ? 'err' : count ? 'warn' : 'ok');
  } else if (action === 'hd-decision') {
    if (!r) return;
    if (r.price == null) { toast('没有行情，不生成决策', r.name + ' 取不到现价。决策要现价、止损位和当日回撤，缺一样就不算——先刷新行情。', 'warn'); return; }
    r.decision = { running: true, action: 'hold', conf: null, at: '2026-11-16 15:13' };
    state.hdId = Number(r.id);
    state.hdTab = 'basis';
    renderView();
    syncHdHash();
    toast('卖出决策任务已提交', 'sell_decision 在后台跑，完成后回到这一页替换成结论。决策只是参考，卖出一刀必须由你人工下。', 'run');
  } else if (action === 'hd-row-op') {
    if (r) hdOpenForm(r.id, hdVerdict(r) === 'exit' ? 'exit' : 'reduce', true);
  } else if (action === 'hd-op') {
    if (r && HD_OPS[kind]) hdOpenForm(r.id, kind);
  } else if (action === 'hd-op-ok') {
    if (!r || !HD_OPS[kind]) return;
    const v = hdReadForm(r, kind);
    if (!v) return;
    state.hdForm = Object.assign({}, state.hdForm, { confirm: true, values: v });
    renderView();
    const box = document.querySelector('#hd-detail .inline-confirm');
    if (box) box.scrollIntoView({ block: 'nearest' });
  } else if (action === 'hd-op-confirm') {
    if (!r || !state.hdForm || !state.hdForm.values) return;
    const v = state.hdForm.values;
    const quick = state.hdForm.quick;
    state.hdForm = null;
    const msg = hdApplyOp(r, kind, v);
    if (quick || !hdById(r.id)) hdQuickDone(r, msg, kind);
    else { renderView(); syncHdHash(); toast('已记录', msg + '，已更新下方买卖记录。', 'ok'); }
  } else if (action === 'hd-op-cancel') {
    if (state.hdForm && state.hdForm.confirm) {
      state.hdForm = Object.assign({}, state.hdForm, { confirm: false, values: null });
    } else {
      state.hdForm = null;
    }
    renderView();
  } else if (action === 'hd-add') {
    state.hdNewPending = null;
    openDrawer('hd-new', {});
  } else if (action === 'hd-new-save') {
    const v = hdReadNew();
    if (!v) return;
    if (v.warns.length) {
      state.hdNewPending = { v: v, warns: v.warns };
      openDrawer('hd-new', v);
      toast('先看一下风险', '这几条不拦你，但会立刻影响明天的红线判定；确认后可以照样记。', 'warn');
      return;
    }
    hdCommitNew(v);
  } else if (action === 'hd-new-check') {
    const p = state.hdNewPending;
    state.hdNewPending = null;
    openDrawer('hd-new', p ? p.v : {});
  } else if (action === 'hd-new-force') {
    const p = state.hdNewPending;
    if (p) hdCommitNew(p.v);
  } else if (action === 'hd-ocr') {
    state.hdOcrDone = false;
    state.hdOcrRows = null;
    openDrawer('hd-ocr');
  } else if (action === 'hd-ocr-run') {
    state.hdOcrDone = true;
    state.hdOcrRows = [
      { code: '000063', name: '中兴通讯', price: 38.60, shares: 500, note: '识别置信度 0.94 · 成本列取的是持仓均价' },
      { code: '688111', name: '金山办公', price: 285.40, shares: 100, note: '识别置信度 0.71 · 小数点容易被吃掉，重点核对这一行' }
    ];
    openDrawer('hd-ocr');
  } else if (action === 'hd-ocr-save') {
    if (state.hdOcrRows) hdOcrCommit();
  } else if (action === 'hd-baseline') {
    openDrawer('hd-baseline');
  } else if (action === 'hd-baseline-save') {
    const tEl = $('#hd-b-total'), cEl = $('#hd-b-cash');
    const total = tEl ? parseFloat(tEl.value) : NaN;
    const cash = cEl ? parseFloat(cEl.value) : NaN;
    if (!(total > 0)) { toast('总资产要填正数', '总资产是单票占比与总仓位的分母，空着或 0 就没法算红线。', 'warn'); return; }
    if (cash < 0 || cash > total) { toast('可用现金不在总资产里', '现金要在 0 ～ 总资产之间：现在总资产 ' + hdMoney(total) + ' 元。', 'warn'); return; }
    const before = hdTotalShare();
    const mv = hdTotalMv();
    const gap = Math.round(total - cash - mv);
    state.hdAccount.total = total;
    state.hdAccount.cash = cash;
    closeDrawer();
    renderView();
    const after = hdTotalShare();
    toast('账户基线已更新', '总仓位由 ' + before.toFixed(1) + '% 重算为 ' + after.toFixed(1) + '%（C2 上限 ' + HD_CAP.total + '%）。每只票的结论、单票占比和组合哨兵都跟着重算了。' +
      (Math.abs(gap) > total * 0.01
        ? '另外：总资产 ' + hdMoney(total) + ' 减现金 ' + hdMoney(cash) + ' 和持仓市值 ' + hdMoney(mv) + ' 差 ' + hdMoney(gap) + ' 元，已按你填的券商数字保存，差额以「其他资产」理解，不影响红线计算。'
        : ''),
      after > HD_CAP.total ? 'err' : 'ok');
  } else {
    toast('这个按钮还没接线', action + ' 没有对应的处理逻辑：原型里点到就说明漏了，这一轮补上。', 'warn');
  }
}

/* ---------- AI 模拟操盘：与真实持仓完全隔离的 paper 账本 ---------- */
/* 成交约束口径取自后端 paper_execution.py，改数值等于改模拟盘行为，这里只做展示对齐 */
const PP_RULES = {
  lot: 100, commissionRate: 0.0003, commissionMin: 5, stampRate: 0.0005, transferRate: 0.00001,
  slipBps: 5, lotTolerance: 0.05, freshMinutes: 10, monitorMinutes: 5,
  addTriggerPct: 3, firstTakePct: 8, mainTakePct: 15, hardStopPct: -8, trailStopPct: 5,
  firstReduceRatio: 0.30, firstAllocationPct: 10, addAllocationPct: 10, maxAllocationPct: 20
};

/* 键名与后端 labels / reject_reason 一致，原型不另造一套词 */
const PP_LABELS = {
  buy: '买入', sell: '卖出', add: '加仓', reduce: '减仓', exit: '清仓', hold: '继续持有',
  partial: '部分减仓', filled: '已成交', rejected: '已拒绝', skipped: '本轮跳过', pending: '待处理',
  ok: '已获取', error: '获取失败', unavailable: '行情暂缺', stale: '行情已过期',
  partial_or_unavailable: '行情不完整', no_data: '暂无数据',
  active: '运行中', paused: '已暂停', archived: '已归档',
  live_paper: '实时模拟', historical_replay: '历史回放', historical_snapshot: '历史冻结快照',
  tencent: '腾讯行情', eastmoney_batch: '东财批量行情', spot_quote: '单股行情', mixed: '多来源', none: '暂无来源',
  info: '常规关注', warning: '风险提醒', critical: '紧急风险',
  research: '研究取证', monitor: '监控信号 + 卖出研判', position_action: 'AI 持仓动作',
  candidate_pool: '候选池自主加减仓', current_gate: '现有门禁链路',
  get_quote: '实时行情', get_daily_kline: '日K线', get_news: '新闻公告', get_financial: '财务指标',
  get_fund_flow: '资金流向', search_knowledge: '知识库检索', get_sector_regime: '板块环境',
  get_position_risk: '持仓风险', 'paper_web.search': '联网检索',
  limit_up: '涨停无法买入', limit_down: '跌停无法卖出', suspended: '标的停牌', price_missing: '价格缺失',
  future_data: '资料晚于决策时点', not_tradeable: '未通过可建仓验证', already_holding: '已有模拟持仓',
  plan_or_price_missing: '建仓计划或价格缺失', cash_or_plan_position_too_small: '资金或计划仓位不足一手',
  t_plus_one_or_no_lot: '当日买入不可卖出，或可卖数量不足一手', no_position: '没有对应模拟持仓',
  ai_add_blocked_cash_or_lot: '加仓换算后不足一手或现金不够', single_stock_target_reached: '单票目标仓位已用满',
  ai_reduce_unavailable_or_invalid: '可卖不足一手，或模型未给出减仓比例',
  ai_reduce_below_one_lot: '减仓换算后不足一手', llm_unavailable: 'AI 研判暂不可用',
  opened: '建仓后持有', added: '已加仓', trailing_protection: '止盈保护', hard_stop_loss: '硬止损触发',
  main_take_profit: '主止盈触发', control_hold: '按计划观察', ai_add: 'AI 判定加仓',
  ai_reduce: 'AI 判定减仓', ai_exit: 'AI 判定清仓',
  pending: '待AI审核', pass: 'AI审核通过', fail: 'AI审核未通过'
};
/* 影子验证用独立词表：active / pending 在账户与审核状态里另有含义，混用会显示成「运行中」「待AI审核」 */
const PP_SHADOW_LABELS = { not_started: '影子验证未进入', pending: '影子验证待启动', active: '影子验证中', blocked: '影子验证被拦截' };
function ppShadowLabel(value) { return PP_SHADOW_LABELS[String(value)] || '影子验证状态未记录'; }
function ppLabel(value, fallback) {
  if (value == null || value === '') return fallback || '暂未记录';
  return PP_LABELS[String(value)] || String(value);
}

const PP_TABS = [
  ['positions', '模拟持仓'], ['executions', '模拟流水'], ['contexts', '研究取证'],
  ['alerts', '模拟告警'], ['reviews', '模拟复盘']
];

/* 每一格是一次可核验的行情快照；null 表示本轮没取到价，可用上一轮价回填成参考行情 */
const PP_ACCOUNT_SEED = [
  {
    id: 901, name: '候选池自主加仓 · 11月', status: 'active', variant: 'candidate_pool',
    mode: 'live_paper', quoteSource: 'tencent', initialCash: 300000, createdAt: '2026-11-05',
    model: 'action-v1 / qwen-max', ruleVersion: 'paper-execution-v1', cursor: 2,
    schedule: { every: 5, window: '交易日 09:30-11:30 / 13:00-15:00', next: '2026-11-17 09:33' },
    slots: [
      { d: '2026-11-13', t: '10:35' }, { d: '2026-11-13', t: '13:40' }, { d: '2026-11-16', t: '09:35' },
      { d: '2026-11-16', t: '10:20' }, { d: '2026-11-16', t: '13:30' }, { d: '2026-11-16', t: '14:55' },
      { d: '2026-11-16', t: '15:00' }
    ],
    universe: {
      '603501': { name: '韦尔股份', prevClose: 119.90, series: [114.60, 116.20, 121.40, 123.00, 122.20, 124.60, 125.10] },
      '002049': { name: '紫光国微', prevClose: 69.30, series: [{ p: 76.20, limitUp: true }, 78.90, 80.60, null, 81.90, 79.80, 80.20] },
      '300750': { name: '宁德时代', prevClose: 213.40, series: [214.80, 216.30, 219.50, 221.20, 218.40, 216.90, 217.50] },
      '688041': { name: '海光信息', prevClose: 57.30, limitPct: 20, series: [57.90, 58.40, 59.60, 61.20, 60.40, { p: null, ref: false }, 62.30] },
      '601012': { name: '隆基绿能', prevClose: 18.70, series: [18.90, 18.95, 19.00, 19.05, 18.85, 19.20, 19.10] },
      '601138': { name: '工业富联', prevClose: 23.60, series: [23.90, 24.10, 24.30, 24.60, { p: 25.96, limitUp: true }, 25.40, 25.60] },
      '600584': { name: '长电科技', prevClose: 41.20, series: [41.40, 41.80, 42.10, 42.60, 43.10, 42.80, 43.20] },
      '002371': { name: '北方华创', prevClose: 412.00, series: [415.20, 418.60, 421.00, 424.50, 419.80, 427.30, 430.10] }
    },
    seeds: [
      { d: '2026-11-05', t: '09:41', code: '601012', side: 'buy', price: 18.60, shares: 1000, status: 'filled', planId: 805, scoreId: 5410, candidateId: 'C-1104-601012', intent: '首仓 10%', note: '候选 11-04 批次评分 76，成交额闸门通过' },
      { d: '2026-11-09', t: '09:36', code: '603501', side: 'buy', price: 112.40, shares: 200, status: 'filled', planId: 812, scoreId: 5455, candidateId: 'C-1106-603501', intent: '首仓 10%' },
      { d: '2026-11-09', t: '10:05', code: '002049', side: 'buy', price: 76.80, shares: 300, status: 'filled', planId: 815, scoreId: 5461, candidateId: 'C-1106-002049', intent: '首仓 10%' },
      { d: '2026-11-10', t: '09:38', code: '300750', side: 'buy', price: 209.60, shares: 200, status: 'filled', planId: 818, scoreId: 5468, candidateId: 'C-1109-300750', intent: '首仓 10%' },
      { d: '2026-11-12', t: '09:44', code: '688041', side: 'buy', price: 55.80, shares: 500, status: 'filled', planId: 826, scoreId: 5489, candidateId: 'C-1111-688041', intent: '首仓 10%' },
      { d: '2026-11-13', t: '10:35', code: '002049', side: 'buy', price: 76.20, shares: 0, status: 'rejected', reason: 'limit_up', intent: '加仓 10%', contextId: 5105 },
      { d: '2026-11-13', t: '13:44', code: '300750', side: 'sell', price: 216.30, shares: 200, status: 'filled', intent: 'AI 判定清仓', contextId: 5102, note: '模型给出 exit，代码只按可卖 200 股换算' },
      { d: '2026-11-16', t: '09:31', code: '688041', side: 'sell', price: 59.40, shares: 100, status: 'filled', intent: 'AI 减仓 30%', contextId: 5103 },
      { d: '2026-11-16', t: '09:34', code: '600584', side: 'buy', price: 42.10, shares: 0, status: 'rejected', reason: 'not_tradeable', intent: '首仓 10%', contextId: 5104, note: '候选成交额 3.2 亿，低于 5 亿闸门（RC-1051）' },
      { d: '2026-11-16', t: '09:35', code: '603501', side: 'buy', price: 120.10, shares: 200, status: 'filled', intent: 'AI 加仓 10%', contextId: 5101 },
      { d: '2026-11-16', t: '09:36', code: '600584', side: 'sell', price: 42.10, shares: 0, status: 'rejected', reason: 'no_position', intent: 'AI 减仓 30%', note: '建仓被拒后队列仍挂着卖出意图；代码不猜持仓，直接拒绝留痕' }
    ],
    plans: {
      '603501': { planId: 812, phase: 'added', addCount: 1, allocatedPct: 20, theme: '半导体 CIS 主线' },
      '002049': { planId: 815, phase: 'opened', addCount: 0, allocatedPct: 10, theme: '特种芯片国产替代' },
      '688041': { planId: 826, phase: 'ai_reduce', addCount: 0, allocatedPct: 10, theme: '算力芯片' },
      '601012': { planId: 805, phase: 'opened', addCount: 0, allocatedPct: 10, theme: '光伏组件' }
    },
    intents: [
      { code: '601138', side: 'buy', allocationPct: 10, candidateId: 'C-1116-601138', scoreId: 5521, planId: 861, from: '候选池 11-16 批次 · 评分 86' },
      { code: '300750', side: 'buy', allocationPct: 10, candidateId: 'C-1116-300750', scoreId: 5524, planId: 863, from: '离场后重新达标，计划已重算' },
      { code: '002049', side: 'buy', action: 'open', allocationPct: 10, candidateId: 'C-1116-002049', scoreId: 5519, planId: 862, from: '同一标的重复建仓意图' },
      { code: '600584', side: 'buy', allocationPct: 10, candidateId: 'C-1116-600584', scoreId: 5527, planId: null, from: '候选未通过可建仓验证' },
      { code: '601012', side: 'buy', allocationPct: 0.2, candidateId: 'C-1116-601012', scoreId: 5530, planId: 865, from: '已持仓再加仓，但目标金额换算后不足一手' },
      { code: '002371', side: 'buy', allocationPct: 0.3, candidateId: 'C-1116-002371', scoreId: 5531, planId: 866, from: '新候选首仓，但模型给的目标仓位过小' },
      { code: '603501', side: 'buy', action: 'add', allocationPct: 10, candidateId: 'C-1116-603501', scoreId: 5532, planId: 812, from: '计划目标仓位已到 20% 上限，模型仍想再加一档' },
      { code: '603501', side: 'sell', reduceRatio: null, from: '模型给了减仓动作却没给比例' }
    ],
    contexts: [
      {
        id: 5101, code: '603501', d: '2026-11-16', t: '09:35', stage: 'position_action', mode: 'live_paper',
        factAsOf: '2026-11-16 09:35', tools: [
          { tool: 'get_quote', status: 'ok', summary: '现价 120.10，涨 +0.17%' },
          { tool: 'get_daily_kline', status: 'ok', summary: '60 根日K，站上 20 日均线' },
          { tool: 'get_news', status: 'ok', summary: '3 条公告与新闻，最近一条 11-15 21:04' },
          { tool: 'get_fund_flow', status: 'ok', summary: '主力净流入 3.1 亿' },
          { tool: 'get_sector_regime', status: 'ok', summary: '半导体板块环境：放量但拥挤度偏高' },
          { tool: 'search_knowledge', status: 'ok', summary: '命中 4 条：加仓触发档、集中度上限' },
          { tool: 'paper_web.search', status: 'ok', summary: '联网检索 2 条来源' }
        ],
        web: [
          { title: '半导体设备招标放量，产业链订单能见度提升', source: '财联社', url: 'https://www.cls.cn/detail/2031145', publishedAt: '2026-11-15 21:04', excerpt: '多家封测与设备厂商披露 Q4 订单环比提升。', hash: 'a17f…9c20' },
          { title: 'CIS 传感器四季度出货指引上调', source: '上海证券报', url: 'https://paper.cnstock.com/html/2026-11/16/content_1', publishedAt: '2026-11-16 07:20', excerpt: '公司指引上调 6%，主要来自动车与安防需求。', hash: 'b48d…11ae' }
        ],
        decision: { action: 'add', allocationPct: 10, confidence: 'medium', reasons: [
          '浮盈 +5.2% 超过加仓触发档 +3%，趋势维度未破位。',
          '联网证据显示订单能见度上调，但板块拥挤度偏高，因此只按一档 10% 加。'
        ], riskNote: '若明日低开跌破 118，本档加仓的保护价需要随移动止损上移。' }
      },
      {
        id: 5102, code: '300750', d: '2026-11-13', t: '13:44', stage: 'position_action', mode: 'live_paper',
        factAsOf: '2026-11-13 13:40', tools: [
          { tool: 'get_quote', status: 'ok', summary: '现价 216.30，跌 -1.4%' },
          { tool: 'get_daily_kline', status: 'ok', summary: '跌破 20 日均线，量能放大' },
          { tool: 'get_fund_flow', status: 'ok', summary: '主力连续 3 日净流出' },
          { tool: 'search_knowledge', status: 'ok', summary: '命中 2 条：动力电池排产下修' }
        ],
        web: [{ title: '动力电池排产环比下修', source: '东方财富', url: 'https://finance.eastmoney.com/a/20261113001.html', publishedAt: '2026-11-13 11:12', excerpt: '11 月排产环比 -4.2%。', hash: 'c02e…77b1' }],
        decision: { action: 'exit', confidence: 'high', reasons: [
          '日线跌破 20 日均线且下跌放量，趋势维度转为风险。',
          '资金与板块两个维度同向，模型判定不再等反弹，直接清仓。'
        ], riskNote: '清仓后若板块资金回流需要重新走候选池验证，不能直接回补。' }
      },
      {
        id: 5103, code: '688041', d: '2026-11-16', t: '09:31', stage: 'position_action', mode: 'live_paper',
        factAsOf: '2026-11-16 09:30', tools: [
          { tool: 'get_quote', status: 'ok', summary: '现价 59.40，涨 +1.7%' },
          { tool: 'get_daily_kline', status: 'ok', summary: '高位放量滞涨' },
          { tool: 'get_position_risk', status: 'ok', summary: '单票占模拟总资产 11.8%' },
          { tool: 'paper_web.search', status: 'error', summary: '', error: '联网检索超时 8s，降级为站内证据' }
        ],
        web: [],
        decision: { action: 'reduce', reduceRatio: 0.30, confidence: 'medium', reasons: [
          '浮盈 +6.4% 但滞涨放量，先落袋三成。',
          '联网证据缺失，模型置信度降到中档，减仓比例不放大。'
        ], riskNote: '剩余仓位按移动止损 5% 保护。' }
      },
      {
        id: 5104, code: '600584', d: '2026-11-16', t: '09:34', stage: 'research', mode: 'live_paper',
        factAsOf: '2026-11-16 09:33', tools: [
          { tool: 'get_quote', status: 'ok', summary: '现价 42.10' },
          { tool: 'search_knowledge', status: 'ok', summary: '命中硬规则 RC-1051：候选池最低成交额 5 亿' },
          { tool: 'get_fund_flow', status: 'ok', summary: '成交额 3.2 亿，未达闸门' }
        ],
        web: [],
        decision: { action: 'hold', confidence: 'high', reasons: ['可建仓验证未通过，本次不产生建仓意图。'], riskNote: '' }
      },
      {
        id: 5105, code: '002049', d: '2026-11-13', t: '10:35', stage: 'research', mode: 'live_paper',
        factAsOf: '2026-11-13 10:35', tools: [
          { tool: 'get_quote', status: 'ok', summary: '现价 76.20，涨停（+9.96%）' },
          { tool: 'get_news', status: 'error', summary: '', error: '新闻接口返回空数据' },
          { tool: 'get_sector_regime', status: 'ok', summary: '特种芯片板块资金净流入' }
        ],
        web: [],
        decision: { action: 'add', allocationPct: 10, confidence: 'low', reasons: ['涨停封板，买入意图无法成交。'], riskNote: '涨停未开板前不追。' }
      },
      {
        id: 5106, code: '603501', d: '2026-11-16', t: '09:33', stage: 'monitor', mode: 'live_paper',
        factAsOf: '2026-11-16 09:33', tools: [
          { tool: 'get_quote', status: 'ok', summary: '现价 119.80' },
          { tool: 'get_news', status: 'ok', summary: '取到 4 条，其中 1 条发布于 2026-11-17' }
        ],
        web: [{ title: '（回放隔离）一条晚于决策时点的公告', source: '站内缓存', url: '', publishedAt: '2026-11-17 08:00', excerpt: '事实时点晚于本次决策时点，已被拒绝进入证据集。', hash: 'd93a…04f2' }],
        rejected: 'future_data',
        decision: { action: 'hold', confidence: 'low', reasons: ['冻结事实校验未通过：1 条新闻发布于 2026-11-17，晚于决策时点。'], riskNote: '本轮不产生买卖动作，下一轮重新取证。' }
      }
    ],
    alerts: [
      { id: 7001, code: '603501', d: '2026-11-16', severity: 'info', source: 'paper_monitor', contextId: 5101, message: 'AI 判定 加仓：浮盈 +5.2% 达到加仓触发档，整手换算后买入 200 股' },
      { id: 7002, code: '603501', d: '2026-11-16', severity: 'warning', source: 'paper_monitor', contextId: 5106, message: '模拟分析未完成：冻结事实中有 1 条新闻发布于 2026-11-17，晚于本次决策时点，已拒绝使用' },
      { id: 7003, code: '600584', d: '2026-11-16', severity: 'warning', source: 'paper_execution', contextId: 5104, message: '模拟执行已拒绝：未通过可建仓验证，候选成交额 3.2 亿低于 5 亿闸门' },
      { id: 7004, code: '300750', d: '2026-11-13', severity: 'critical', source: 'paper_monitor', contextId: 5102, message: 'AI 判定 清仓：跌破 20 日均线且板块资金净流出，已按 216.30 卖出全部 200 股' }
    ],
    reviews: [
      {
        id: 8801, code: '300750', d: '2026-11-13', execId: null, audit: 'pass', auditMode: 'ai', shadow: 'active',
        candidateId: 'C-1109-300750', scoreId: 5468, planId: 818, factAsOf: '2026-11-13 13:40',
        summary: '清仓后两个交易日反弹 +2.1%，执行本身符合计划，但触发偏晚，利润回吐约 1.4%。',
        lesson: '加仓触发 +3% 与主止盈 +15% 之间缺少中间档，趋势破位时只能整档离场。',
        gaps: [], auditReason: '候选、评分、建仓计划来源齐全，交易日期与事实时点一致，未发现未来数据。',
        confidence: 82, support: '同口径 12 笔清仓案例 T+5 平均 -1.4%，方向一致。',
        dissent: '本案例单笔成交，反弹可能来自板块 beta 而非个股。',
        boundary: '板块资金净流入转正时，破位结论需要重新评估。',
        shadowNote: '只作为影子案例参与验证，不代表正式规则已采纳。'
      },
      {
        id: 8802, code: '688041', d: '2026-11-16', execId: null, audit: 'fail', auditMode: 'ai', shadow: 'blocked',
        candidateId: 'C-1111-688041', scoreId: 5489, planId: null, factAsOf: '2026-11-16 09:30',
        summary: '减仓 30% 后价格回落，落袋方向正确，但建仓计划来源缺失。',
        lesson: '减仓比例应绑定持仓成本与移动止损，而不是只看浮盈档位。',
        gaps: ['missing:plan_id'], auditReason: '事实闸门未通过：missing:plan_id',
        confidence: 40, support: '', dissent: '',
        boundary: '补齐建仓计划来源后可重新送审。', shadowNote: ''
      },
      {
        id: 8803, code: '600584', d: '2026-11-16', execId: null, audit: 'pending', auditMode: 'ai', shadow: 'not_started',
        candidateId: 'C-1116-600584', scoreId: null, planId: 866, factAsOf: '2026-11-16 09:34',
        summary: '建仓被成交额闸门拒绝，需要判断 5 亿门槛对封测类标的是否过严。',
        lesson: '闸门按全市场统一口径，板块差异需要另做分层验证。',
        gaps: ['missing:score_id'], auditReason: '', confidence: null, support: '', dissent: '', boundary: '',
        shadowNote: '收盘后的 AI 审核任务会自动处理这一条。'
      }
    ],
    runs: [
      { at: '2026-11-13 10:35', kind: 'monitor', filled: 0, rejected: 1, skipped: 0 },
      { at: '2026-11-13 13:44', kind: 'monitor', filled: 1, rejected: 0, skipped: 0 },
      { at: '2026-11-13 15:30', kind: 'review', filled: 0, rejected: 0, skipped: 0, note: '模拟复盘 AI 审核：2 条送审，1 条通过' },
      { at: '2026-11-16 09:34', kind: 'run', filled: 1, rejected: 2, skipped: 0 },
      { at: '2026-11-16 09:35', kind: 'monitor', filled: 2, rejected: 0, skipped: 0 }
    ]
  },
  {
    id: 902, name: '现有门禁 · 9月历史回放', status: 'paused', variant: 'current_gate',
    mode: 'historical_replay', quoteSource: 'historical_snapshot', initialCash: 400000, createdAt: '2026-09-15',
    model: 'monitor-v3 + sell-v2', ruleVersion: 'paper-execution-v1', cursor: 2,
    schedule: { every: 5, window: '回放按已冻结的 09-15 ~ 09-16 快照逐轮重放', next: '继续运行后从 2026-09-16 11:05 接着放' },
    replayNote: '历史回放只用当日冻结事实：不回填今天的持仓、行情和知识库。',
    slots: [
      { d: '2026-09-15', t: '10:35' }, { d: '2026-09-15', t: '14:20' }, { d: '2026-09-16', t: '09:40' },
      { d: '2026-09-16', t: '11:05' }, { d: '2026-09-16', t: '14:50' }
    ],
    universe: {
      '002415': { name: '海康威视', prevClose: 28.40, series: [28.60, 28.75, 29.10, 29.40, 30.20] },
      '601012': { name: '隆基绿能', prevClose: 17.30, series: [17.40, 17.95, 18.05, 16.85, 15.95] },
      '300750': { name: '宁德时代', prevClose: 204.00, series: [205.40, 206.10, 207.50, 204.20, 202.60] }
    },
    seeds: [
      { d: '2026-09-15', t: '10:40', code: '002415', side: 'buy', price: 28.60, shares: 1200, status: 'filled', planId: 776, scoreId: 5102, candidateId: 'C-0914-002415', intent: '计划 776 首批 8%' },
      { d: '2026-09-15', t: '14:25', code: '601012', side: 'buy', price: 17.40, shares: 3000, status: 'filled', planId: 778, scoreId: 5108, candidateId: 'C-0914-601012', intent: '计划 778 首批 10%' },
      { d: '2026-09-16', t: '09:35', code: '601012', side: 'sell', price: 18.05, shares: 1500, status: 'filled', intent: '监控信号 → 卖出研判：部分减仓 50%', contextId: 5201 },
      { d: '2026-09-16', t: '09:38', code: '300750', side: 'buy', price: 205.40, shares: 200, status: 'filled', planId: 780, scoreId: 5111, candidateId: 'C-0915-300750', intent: '计划 780 首批 10%' },
      { d: '2026-09-16', t: '09:40', code: '300750', side: 'sell', price: 205.90, shares: 0, status: 'rejected', reason: 't_plus_one_or_no_lot', intent: '卖出研判：部分减仓 50%', contextId: 5202 }
    ],
    plans: {
      '002415': { planId: 776, phase: 'opened', addCount: 0, allocatedPct: 8, theme: '安防与AIoT' },
      '601012': { planId: 778, phase: 'added', addCount: 0, allocatedPct: 10, theme: '光伏组件' },
      '300750': { planId: 780, phase: 'opened', addCount: 0, allocatedPct: 10, theme: '动力电池' }
    },
    intents: [],
    contexts: [
      {
        id: 5201, code: '601012', d: '2026-09-16', t: '09:35', stage: 'monitor', mode: 'historical_replay',
        factAsOf: '2026-09-16 09:35', tools: [
          { tool: 'historical_snapshot', status: 'ok', summary: '当日冻结快照：现价 18.05，涨 +1.7%' },
          { tool: 'get_daily_kline', status: 'ok', summary: '60 根日K，触及第二档移动止盈' },
          { tool: 'get_news', status: 'error', summary: '', error: '回放模式不取当日新闻，避免未来数据' }
        ],
        web: [],
        signal: { action: 'reduce', severity: 'warning', message: '移动止盈第二档命中，浮盈 +3.7%' },
        decision: { action: 'partial', reduceRatio: 0.50, confidence: 'medium', reasons: [
          '监控信号要求减仓，卖出研判按第二档比例出一半。',
          '回放口径：只用 09-16 冻结事实，不用今天的行情回填。'
        ], riskNote: '剩余 1500 股按第二档上移后的止盈位保护。' }
      },
      {
        id: 5202, code: '300750', d: '2026-09-16', t: '09:40', stage: 'monitor', mode: 'historical_replay',
        factAsOf: '2026-09-16 09:40', tools: [
          { tool: 'historical_snapshot', status: 'ok', summary: '现价 205.90' },
          { tool: 'get_position_risk', status: 'ok', summary: '可卖 0 股（当日买入未解冻）' }
        ],
        web: [],
        signal: { action: 'reduce', severity: 'info', message: '冲高回落 1.2%，实验性影子信号' },
        decision: { action: 'partial', reduceRatio: 0.50, confidence: 'low', reasons: ['影子规则实验，不代表正式链路。'], riskNote: '' }
      }
    ],
    alerts: [
      { id: 5301, code: '601012', d: '2026-09-16', severity: 'warning', source: 'paper_sell', contextId: 5201, message: '模拟卖出已成交：监控信号 + 卖出研判，减仓 50%，1500 股 @18.04' },
      { id: 5302, code: '300750', d: '2026-09-16', severity: 'warning', source: 'paper_execution', contextId: 5202, message: '模拟卖出被拒：当日买入不可卖出，或可卖数量不足一手' }
    ],
    reviews: [
      {
        id: 8901, code: '601012', d: '2026-09-16', execId: null, audit: 'pending', auditMode: 'ai', shadow: 'not_started',
        candidateId: 'C-0914-601012', scoreId: 5108, planId: 778, factAsOf: '2026-09-16 09:35',
        summary: '第二档止盈减半后价格回落 6.5%，落袋有效；但同日另一笔 T+1 卖出被拒，说明解冻口径要在计划里写明。',
        lesson: '移动止盈分档在震荡下跌段优于一次性清仓。', gaps: [], auditReason: '', confidence: null,
        support: '', dissent: '', boundary: '', shadowNote: '恢复运行后由收盘审核任务处理。'
      }
    ],
    runs: [
      { at: '2026-09-15 10:40', kind: 'run', filled: 2, rejected: 0, skipped: 0 },
      { at: '2026-09-16 09:40', kind: 'monitor', filled: 1, rejected: 1, skipped: 0 }
    ]
  },
  {
    id: 903, name: '10月对照盘（已归档）', status: 'archived', variant: 'candidate_pool',
    mode: 'live_paper', quoteSource: 'tencent', initialCash: 200000, createdAt: '2026-10-20',
    model: 'action-v1 / qwen-max', ruleVersion: 'paper-execution-v1', cursor: 2,
    archivedAt: '2026-11-06 15:10', archiveReason: '改用候选池变体另开账户做对照，旧账户停止自动运行，历史全部保留',
    schedule: { every: 5, window: '已停止', next: '—' },
    slots: [
      { d: '2026-10-20', t: '09:40' }, { d: '2026-10-23', t: '14:10' }, { d: '2026-11-06', t: '09:50' }
    ],
    universe: {
      '601869': { name: '长飞光纤', prevClose: 29.60, series: [29.80, 31.20, 32.10] },
      '600893': { name: '航发动力', prevClose: 42.10, series: [42.30, 40.90, 39.10] }
    },
    seeds: [
      { d: '2026-10-20', t: '09:41', code: '601869', side: 'buy', price: 29.80, shares: 1000, status: 'filled', planId: 702, scoreId: 4980, candidateId: 'C-1019-601869', intent: '首仓 10%' },
      { d: '2026-10-20', t: '10:12', code: '600893', side: 'buy', price: 42.30, shares: 500, status: 'filled', planId: 705, scoreId: 4986, candidateId: 'C-1019-600893', intent: '首仓 10%' },
      { d: '2026-11-06', t: '09:48', code: '601869', side: 'sell', price: 32.10, shares: 1000, status: 'filled', intent: 'AI 判定清仓（主止盈）', contextId: 5401 },
      { d: '2026-11-06', t: '09:49', code: '600893', side: 'sell', price: 39.10, shares: 500, status: 'filled', intent: 'AI 判定清仓（硬止损 -8%）', contextId: 5401 }
    ],
    plans: {},
    intents: [],
    contexts: [
      {
        id: 5401, code: '600893', d: '2026-11-06', t: '09:49', stage: 'position_action', mode: 'live_paper',
        factAsOf: '2026-11-06 09:48', tools: [
          { tool: 'get_quote', status: 'ok', summary: '现价 39.10，跌 -1.2%' },
          { tool: 'get_daily_kline', status: 'ok', summary: '跌破成本 ×0.92 的硬止损位' }
        ],
        web: [],
        decision: { action: 'exit', confidence: 'high', reasons: ['硬止损触发，按规则离场，不讨论基本面。'], riskNote: '' }
      }
    ],
    alerts: [
      { id: 5501, code: '600893', d: '2026-11-06', severity: 'critical', source: 'paper_monitor', contextId: 5401, message: 'AI 判定 清仓：硬止损触发，已按 39.10 卖出全部 500 股' }
    ],
    reviews: [
      {
        id: 8702, code: '600893', d: '2026-11-06', execId: null, audit: 'pass', auditMode: 'manual', shadow: 'active',
        candidateId: 'C-1019-600893', scoreId: 4986, planId: 705, factAsOf: '2026-11-06 09:48',
        summary: '硬止损离场后继续下跌 4.1%，规则有效；同批长飞光纤止盈清仓错过后续 6% 涨幅。',
        lesson: '主止盈档位对趋势股偏紧，需要按板块分层再验证。',
        gaps: [], auditReason: '人工复审：AI 首轮因样本数偏少判未通过，但两笔离场方向都被后续走势验证，同意进入影子。',
        confidence: 74, support: '', dissent: '样本只有 2 笔，板块外推不成立。', boundary: '趋势板块与震荡板块需分开统计。',
        shadowNote: '人工复审覆盖 AI 结论，理由已留痕；仍是影子案例，不是正式规则。'
      }
    ],
    runs: [
      { at: '2026-10-20 10:12', kind: 'run', filled: 2, rejected: 0, skipped: 0 },
      { at: '2026-11-06 09:49', kind: 'monitor', filled: 2, rejected: 0, skipped: 0 },
      { at: '2026-11-06 15:10', kind: 'archive', filled: 0, rejected: 0, skipped: 0, note: '账户暂停并归档，调度不再触发' }
    ]
  }
];

/* ---------- AI 模拟操盘：账本引擎（成交是唯一事实，余额一律回放推导） ---------- */
function ppSigned(v, digits) {
  if (v == null || !isFinite(Number(v))) return '—';
  const d = digits == null ? 2 : digits;
  const n = Number(v);
  return (n > 0 ? '+' : n < 0 ? '-' : '') + Math.abs(n).toFixed(d);
}
function ppAmount(v) {
  if (v == null || !isFinite(Number(v))) return '—';
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function ppPct(v, digits) {
  if (v == null || !isFinite(Number(v))) return '—';
  return ppSigned(v, digits == null ? 2 : digits) + '%';
}
function ppCls(v) { return v == null || !isFinite(Number(v)) ? 'dim' : Number(v) > 0 ? 'wo-up' : Number(v) < 0 ? 'wo-down' : 'dim'; }

function ppFees(side, gross) {
  const commission = Math.max(+(gross * PP_RULES.commissionRate).toFixed(2), PP_RULES.commissionMin);
  const transfer = +(gross * PP_RULES.transferRate).toFixed(2);
  const stamp = side === 'sell' ? +(gross * PP_RULES.stampRate).toFixed(2) : 0;
  return +(commission + transfer + stamp).toFixed(2);
}

function ppData() {
  if (!state.paper) {
    let seq = 9000;
    state.paper = clone(PP_ACCOUNT_SEED).map((acc) => {
      acc.execs = (acc.seeds || []).map((row) => {
        seq += 1;
        const name = (acc.universe[row.code] || {}).name || row.code;
        const gross = +(row.price * row.shares).toFixed(2);
        const fee = row.status === 'filled' ? ppFees(row.side, gross) : 0;
        return Object.assign({}, row, { id: seq, name, gross, fee });
      });
      delete acc.seeds;
      acc.intents = acc.intents || [];
      return acc;
    });
    state.paperSeq = { exec: seq, ctx: 6100, alert: 9100, review: 9200, acc: 910 };
  }
  return state.paper;
}

function ppNextId(kind) {
  ppData();
  state.paperSeq[kind] += 1;
  return state.paperSeq[kind];
}

function ppAccounts(view) {
  return ppData().filter((acc) => (view === 'archived' ? acc.status === 'archived' : acc.status !== 'archived'));
}

function ppAcc() {
  const rows = ppAccounts(state.ppView);
  const hit = rows.filter((acc) => acc.id === state.ppAcc)[0] || rows[0] || ppData()[0];
  state.ppAcc = hit.id;
  return hit;
}

function ppSlot(acc, idx) {
  return acc.slots[Math.min(Math.max(idx, 0), acc.slots.length - 1)];
}

function ppStamp(acc, idx) {
  const slot = ppSlot(acc, idx);
  return slot.d + ' ' + slot.t;
}

function ppQuote(acc, code, idx) {
  const u = acc.universe[code];
  if (!u) return null;
  const i = Math.min(Math.max(idx, 0), acc.slots.length - 1);
  const slot = ppSlot(acc, i);
  const raw = u.series[Math.min(i, u.series.length - 1)];
  const flag = raw && typeof raw === 'object' ? raw : { p: raw };
  const base = {
    code: code, name: u.name, prevClose: u.prevClose, limitPct: u.limitPct || 10,
    date: slot.d, stamp: slot.d + ' ' + slot.t, source: acc.quoteSource
  };
  if (flag.p != null) {
    return Object.assign({}, base, {
      price: flag.p,
      chgPct: +(((flag.p - u.prevClose) / u.prevClose) * 100).toFixed(2),
      limitUp: !!flag.limitUp, limitDown: !!flag.limitDown, suspended: !!flag.suspended,
      status: flag.suspended ? 'suspended' : 'ok', referenceOnly: false
    });
  }
  if (flag.ref !== false) {
    for (let k = i - 1; k >= 0; k -= 1) {
      const prev = ppQuote(acc, code, k);
      if (prev.status === 'ok') {
        return Object.assign({}, base, {
          price: prev.price, chgPct: prev.chgPct, limitUp: false, limitDown: false, suspended: false,
          status: 'stale', referenceOnly: true, date: prev.date, stamp: prev.stamp,
          source: '上一轮有效行情（仅供参考）'
        });
      }
    }
  }
  return Object.assign({}, base, {
    price: null, chgPct: null, limitUp: false, limitDown: false, suspended: false,
    status: 'unavailable', referenceOnly: false
  });
}

function ppReplay(acc) {
  const idx = Math.min(acc.cursor, acc.slots.length - 1);
  const today = ppSlot(acc, idx).d;
  const rows = acc.execs.slice().sort((a, b) => (a.d + a.t).localeCompare(b.d + b.t));
  let cash = Number(acc.initialCash), realized = 0, filled = 0, rejected = 0;
  const map = {};
  rows.forEach((row) => {
    if (row.status !== 'filled') { rejected += 1; return; }
    filled += 1;
    const fee = row.fee || 0;
    if (row.side === 'buy') {
      if (!map[row.code]) {
        map[row.code] = { code: row.code, name: row.name, shares: 0, avg: 0, blocked: 0, realized: 0, openedAt: row.d };
      }
      const p = map[row.code];
      p.avg = +(((p.avg * p.shares) + (row.price * row.shares)) / (p.shares + row.shares)).toFixed(4);
      p.shares += row.shares;
      if (row.d === today) p.blocked += row.shares;
      cash -= row.gross + fee;
    } else {
      const p = map[row.code];
      const gain = +(row.gross - fee - p.avg * row.shares).toFixed(2);
      p.realized = +(p.realized + gain).toFixed(2);
      realized += gain;
      p.shares -= row.shares;
      cash += row.gross - fee;
    }
  });
  const positions = Object.keys(map).map((code) => {
    const p = map[code];
    const plan = (acc.plans || {})[code] || {};
    const costPct = +((p.avg * p.shares / Number(acc.initialCash)) * 100).toFixed(1);
    return Object.assign({}, p, {
      available: p.shares - p.blocked,
      planId: plan.planId || null, theme: plan.theme || '',
      phase: plan.phase || '', addCount: plan.addCount || 0,
      allocatedPct: costPct,
      planAllocPct: plan.allocatedPct == null ? costPct : Number(plan.allocatedPct)
    });
  }).filter((p) => p.shares > 0).sort((a, b) => a.code.localeCompare(b.code));
  const closed = Object.keys(map).filter((code) => map[code].shares <= 0)
    .map((code) => map[code]).sort((a, b) => a.code.localeCompare(b.code));
  return { idx: idx, date: today, stamp: ppStamp(acc, idx), cash: +cash.toFixed(2), realized: +realized.toFixed(2),
    filled: filled, rejected: rejected, positions: positions, closed: closed };
}

function ppProtect(avg) {
  const pct = (v) => +(avg * (1 + v / 100)).toFixed(2);
  return { stop: pct(PP_RULES.hardStopPct), take1: pct(PP_RULES.firstTakePct), take2: pct(PP_RULES.mainTakePct) };
}

function ppValuation(acc) {
  const rep = ppReplay(acc);
  let mv = 0, known = true, referenceOnly = false;
  const factTimes = [];
  const rows = rep.positions.map((pos) => {
    const q = ppQuote(acc, pos.code, rep.idx);
    const price = q.status === 'ok' || q.referenceOnly ? q.price : null;
    const guard = ppProtect(pos.avg);
    if (price == null) known = false;
    else { mv += price * pos.shares; factTimes.push(q.stamp); }
    if (q.referenceOnly) referenceOnly = true;
    return Object.assign({}, pos, {
      quote: q, price: price,
      marketValue: price == null ? null : +(price * pos.shares).toFixed(2),
      pnl: price == null ? null : +((price - pos.avg) * pos.shares).toFixed(2),
      pnlPct: price == null || pos.avg <= 0 ? null : +(((price - pos.avg) / pos.avg) * 100).toFixed(2),
      distStop: price == null ? null : +(((price - guard.stop) / price) * 100).toFixed(2),
      distTake: price == null ? null : +(((guard.take1 - price) / price) * 100).toFixed(2),
      guard: guard
    });
  });
  const equity = known ? +(rep.cash + mv).toFixed(2) : null;
  const pnl = equity == null ? null : +(equity - Number(acc.initialCash)).toFixed(2);
  return {
    rep: rep, rows: rows,
    marketValue: known ? +mv.toFixed(2) : null,
    equity: equity, pnl: pnl,
    pnlPct: pnl == null || Number(acc.initialCash) <= 0 ? null : +((pnl / Number(acc.initialCash)) * 100).toFixed(2),
    unrealized: known ? +(rows.reduce((sum, r) => sum + (r.pnl || 0), 0)).toFixed(2) : null,
    quoteStatus: !known ? 'partial_or_unavailable' : referenceOnly ? 'stale' : 'ok',
    referenceOnly: referenceOnly,
    notice: referenceOnly ? '行情已过期，仅供参考' : !known ? '模拟估值暂不完整' : '',
    factAsOf: factTimes.length ? factTimes.slice().sort()[0] : '—',
    mvLabel: referenceOnly ? '估算模拟市值' : '模拟市值',
    equityLabel: referenceOnly ? '估算模拟总资产' : '模拟总资产'
  };
}

function ppSlip(side, price) {
  const raw = side === 'buy' ? price * (1 + PP_RULES.slipBps / 10000) : price * (1 - PP_RULES.slipBps / 10000);
  return +raw.toFixed(2);
}

/* 执行器只做整手、T+1、现金、费用和涨跌停换算；"何时该动"全部来自研判层 */
function ppExecute(acc, intent, quote, pos, cash) {
  if (!quote || quote.price == null) {
    return { status: 'rejected', reason: 'price_missing', shares: 0, note: '本时点没有可用价格，模拟估值也不完整' };
  }
  if (quote.referenceOnly) {
    return { status: 'rejected', reason: 'price_missing', shares: 0, note: '行情已过期，只能作为参考，不允许用于成交' };
  }
  if (quote.suspended) return { status: 'rejected', reason: 'suspended', shares: 0 };
  const price = ppSlip(intent.side, quote.price);
  if (intent.side === 'buy') {
    if (quote.limitUp) return { status: 'rejected', reason: 'limit_up', shares: 0 };
    if (pos && intent.action !== 'add') return { status: 'rejected', reason: 'already_holding', shares: 0 };
    if (!intent.planId) return { status: 'rejected', reason: 'not_tradeable', shares: 0 };
    const wantPct = Number(intent.allocationPct || 0);
    const planPct = pos ? Number(pos.planAllocPct == null ? pos.allocatedPct : pos.planAllocPct) : 0;
    const headroom = +(PP_RULES.maxAllocationPct - planPct).toFixed(1);
    if (pos && headroom <= 0.05) {
      return { status: 'rejected', reason: 'single_stock_target_reached', shares: 0,
        note: '单票目标仓位上限 ' + PP_RULES.maxAllocationPct + '% 已被计划用满（' + planPct + '%），执行层不再加仓' };
    }
    const allocPct = pos ? +Math.min(wantPct, headroom).toFixed(1) : wantPct;
    const target = Number(acc.initialCash) * allocPct / 100;
    const rawLots = target / (price * PP_RULES.lot);
    let lots = Math.floor(rawLots);
    if (rawLots - lots >= 1 - PP_RULES.lotTolerance) lots = Math.ceil(rawLots);
    let shares = lots * PP_RULES.lot;
    while (shares > 0 && shares * price + ppFees('buy', shares * price) > cash) {
      shares -= PP_RULES.lot;
    }
    if (shares <= 0) {
      return { status: 'rejected', reason: intent.action === 'add' ? 'ai_add_blocked_cash_or_lot' : 'cash_or_plan_position_too_small',
        shares: 0, note: '目标金额 ' + target.toFixed(0) + ' 元换算后不足一手，或现金不够' };
    }
    return { status: 'filled', shares: shares, price: price, allocPct: allocPct,
      note: allocPct + 0.05 < wantPct
        ? '模型要求加仓 ' + wantPct + '%，按单票上限只剩 ' + headroom + '% 压缩到 ' + allocPct + '% 执行' : '' };
  }
  if (!pos) return { status: 'rejected', reason: 'no_position', shares: 0 };
  if (quote.limitDown) return { status: 'rejected', reason: 'limit_down', shares: 0 };
  if (pos.available <= 0) return { status: 'rejected', reason: 't_plus_one_or_no_lot', shares: 0 };
  let shares = pos.shares;
  if (intent.action !== 'exit') {
    const ratio = intent.reduceRatio;
    if (ratio == null || !(ratio > 0 && ratio <= 1)) {
      return { status: 'rejected', reason: 'ai_reduce_unavailable_or_invalid', shares: 0,
        note: '模型未给出减仓比例，代码不代为猜测' };
    }
    shares = Math.floor((pos.available * ratio) / PP_RULES.lot) * PP_RULES.lot;
    if (shares <= 0) {
      return { status: 'rejected', reason: 'ai_reduce_below_one_lot', shares: 0,
        note: '可卖 ' + pos.available + ' 股 × ' + Math.round(ratio * 100) + '% 不足一手' };
    }
  } else {
    shares = pos.available;
  }
  return { status: 'filled', shares: shares, price: price };
}

function ppIntentLabel(action, payload) {
  if (action === 'exit') return 'AI 判定清仓';
  if (action === 'reduce') return 'AI 减仓 ' + Math.round((payload.reduceRatio || 0) * 100) + '%';
  if (action === 'add') return 'AI 加仓 ' + (payload.allocationPct || 0) + '%';
  if (action === 'partial') return '卖出研判：部分减仓 ' + Math.round((payload.reduceRatio || 0) * 100) + '%';
  return 'AI 判定买入 ' + (payload.allocationPct || 0) + '%';
}

function ppDecisionTrace(acc, quote, decided, mode) {
  const runMode = mode || acc.mode;
  const tools = [
    { tool: runMode === 'historical_replay' ? 'historical_snapshot' : 'get_quote',
      status: quote.status === 'ok' ? 'ok' : 'unavailable',
      summary: quote.status === 'ok'
        ? (runMode === 'historical_replay' ? '冻结快照收盘价 ' : '现价 ') + quote.price + '，涨跌 ' + ppSigned(quote.chgPct) + '%'
        : quote.price == null ? '本轮未取到可用价格' : '价格 ' + quote.price + ' 来自更早一轮，仅供参考' },
    { tool: 'get_daily_kline', status: 'ok', summary: '60 根日K，均线与量能随本时点重算' },
    { tool: 'get_position_risk', status: 'ok', summary: '单票目标仓位、可卖数量与现金校验' }
  ];
  if (runMode !== 'historical_replay') {
    tools.push({ tool: 'paper_web.search', status: 'ok', summary: '联网检索 1 条来源，已归档证据哈希' });
  }
  const web = runMode === 'historical_replay' ? [] : [{
    title: '本轮研判引用的公开报道', source: '原型内置证据', url: '',
    publishedAt: quote.stamp, excerpt: '静态原型不联网，正文与哈希为占位；正式链路会保存来源与抓取时间。',
    hash: 'pp' + quote.code
  }];
  return { tools: tools, web: web };
}

function ppCommit(acc, entry) {
  const gross = entry.price && entry.shares ? +(entry.price * entry.shares).toFixed(2) : 0;
  const row = {
    id: ppNextId('exec'), d: entry.d, t: entry.t, code: entry.code,
    name: (acc.universe[entry.code] || {}).name || entry.code,
    side: entry.side, action: entry.action || '', price: entry.price || 0, shares: entry.shares || 0,
    gross: gross, fee: entry.status === 'filled' ? ppFees(entry.side, gross) : 0,
    status: entry.status, reason: entry.reason || '', intent: entry.intent || '',
    contextId: entry.contextId || null, planId: entry.planId || null,
    scoreId: entry.scoreId || null, candidateId: entry.candidateId || null,
    note: entry.note || ''
  };
  acc.execs.push(row);
  return row;
}

/* 一笔卖出复盘的候选/评分/计划来源，来自同一标的最早那笔已成交买入 */
function ppOrigin(acc, code) {
  const buys = acc.execs.filter((r) => r.code === code && r.side === 'buy' && r.status === 'filled' && r.candidateId)
    .sort((a, b) => (a.d + a.t).localeCompare(b.d + b.t));
  return buys[0] || null;
}

function ppAddContext(acc, ctx) {
  const row = Object.assign({ id: ppNextId('ctx'), web: [], tools: [], rejected: '' }, ctx);
  acc.contexts.unshift(row);
  return row;
}

function ppAddAlert(acc, alert) {
  const row = Object.assign({ id: ppNextId('alert'), severity: 'info', source: 'paper_execution' }, alert);
  acc.alerts.unshift(row);
  return row;
}

function ppAddReview(acc, review) {
  const row = Object.assign({
    id: ppNextId('review'), audit: 'pending', auditMode: 'ai', shadow: 'not_started',
    gaps: [], confidence: null, support: '', dissent: '', boundary: '', shadowNote: '', auditReason: ''
  }, review);
  acc.reviews.unshift(row);
  return row;
}

function ppLogRun(acc, entry) {
  acc.runs.unshift(Object.assign({ at: ppStamp(acc, acc.cursor), kind: 'monitor', filled: 0, rejected: 0, skipped: 0 }, entry));
}

function ppApplyPlan(acc, code, action, addedPct) {
  acc.plans = acc.plans || {};
  if (action === 'exit') { delete acc.plans[code]; return; }
  const plan = acc.plans[code] || { planId: null, phase: 'opened', addCount: 0, allocatedPct: 10, theme: '' };
  if (action === 'add') {
    plan.addCount += 1;
    plan.phase = 'added';
    plan.allocatedPct = +Math.min(PP_RULES.maxAllocationPct,
      Number(plan.allocatedPct || 0) + Number(addedPct == null ? PP_RULES.addAllocationPct : addedPct)).toFixed(1);
  }
  if (action === 'reduce' || action === 'partial') plan.phase = 'trailing_protection';
  acc.plans[code] = plan;
}

/* 候选池变体：阈值只用于描述当前档位，动作与幅度由研判层给出 */
function ppDecideAI(acc, pos, quote) {
  if (quote.price == null || quote.referenceOnly) {
    return { action: 'hold', confidence: 'low', reasons: ['本时点没有可用价格，研判不产生买卖动作。'], riskNote: '', noQuote: true };
  }
  const pct = ((quote.price - pos.avg) / pos.avg) * 100;
  const guard = ppProtect(pos.avg);
  if (pct <= PP_RULES.hardStopPct) {
    return { action: 'exit', confidence: 'high', reasons: [
      '浮亏 ' + ppSigned(pct) + '% 已越过硬止损档 ' + PP_RULES.hardStopPct + '%。'],
      riskNote: '硬止损为保护性离场，不讨论基本面。' };
  }
  if (pct >= PP_RULES.mainTakePct) {
    return { action: 'exit', confidence: 'medium', reasons: [
      '浮盈 ' + ppSigned(pct) + '% 命中主止盈档 +' + PP_RULES.mainTakePct + '%，趋势兑现离场。'],
      riskNote: '若板块资金继续净流入需重新走候选池验证。' };
  }
  if (pct >= PP_RULES.firstTakePct) {
    return { action: 'reduce', reduceRatio: PP_RULES.firstReduceRatio, confidence: 'medium', reasons: [
      '浮盈 ' + ppSigned(pct) + '% 落在第一止盈档 +' + PP_RULES.firstTakePct + '% 与主止盈之间，先落袋三成。',
      '剩余仓位改用移动止损 ' + PP_RULES.trailStopPct + '% 保护。' ],
      riskNote: '移动止损位 ' + guard.take1.toFixed(2) + ' 元。' };
  }
  if (pct >= PP_RULES.addTriggerPct) {
    const headroom = +(PP_RULES.maxAllocationPct - Number(pos.planAllocPct == null ? pos.allocatedPct : pos.planAllocPct)).toFixed(1);
    if (headroom <= 0.05) {
      return { action: 'hold', confidence: 'medium', reasons: [
        '浮盈 ' + ppSigned(pct) + '% 达到加仓触发档 +' + PP_RULES.addTriggerPct + '%，但单票目标仓位 '
          + PP_RULES.maxAllocationPct + '% 已被计划用满（' + pos.planAllocPct + '%），本轮不加仓。' ],
        riskNote: '等止盈/止损档触发，或下一轮重新计算计划目标。' };
    }
    const addPct = +Math.min(PP_RULES.addAllocationPct, headroom).toFixed(1);
    return { action: 'add', allocationPct: addPct, confidence: 'medium', reasons: [
      '浮盈 ' + ppSigned(pct) + '% 达到加仓触发档 +' + PP_RULES.addTriggerPct + '%，趋势与量能未破位。',
      '计划目标仓位 ' + pos.planAllocPct + '%，距单票上限 ' + PP_RULES.maxAllocationPct + '% 还剩 ' + headroom + '%，本轮按 '
        + addPct + '% 加仓。' ],
      riskNote: '加仓后成本上移，止损位需要同步重算。' };
  }
  return { action: 'hold', confidence: 'medium', reasons: [
    '浮盈 ' + ppSigned(pct) + '% 未触及 +' + PP_RULES.addTriggerPct + '% 加仓档，也未触及 '
      + PP_RULES.hardStopPct + '% 止损档。' ], riskNote: '持仓保护价：止损 ' + guard.stop.toFixed(2) + ' / 止盈 ' + guard.take1.toFixed(2) + '。' };
}

/* 现有门禁链路：先有监控信号，再由卖出研判决定比例（保留线上口径，便于和候选池对照） */
function ppDecideGate(acc, pos, quote) {
  if (quote.price == null || quote.referenceOnly) {
    return { signal: { action: 'hold', severity: 'info', message: '本时点无可用价格，信号不触发' },
      decision: { action: 'hold', reduceRatio: null, confidence: 'low', reasons: ['缺少可用行情事实。'] }, noQuote: true };
  }
  const pct = ((quote.price - pos.avg) / pos.avg) * 100;
  if (pct <= PP_RULES.hardStopPct) {
    return { signal: { action: 'exit', severity: 'critical', message: '浮亏 ' + ppSigned(pct) + '% 命中硬止损档' },
      decision: { action: 'exit', reduceRatio: 1, confidence: 'high', reasons: ['监控信号要求离场，卖出研判确认全部可卖份额。'] } };
  }
  if (pct >= PP_RULES.mainTakePct) {
    return { signal: { action: 'reduce', severity: 'warning', message: '浮盈 ' + ppSigned(pct) + '% 命中主止盈档' },
      decision: { action: 'partial', reduceRatio: 0.50, confidence: 'medium', reasons: ['按第二档止盈出一半。'] } };
  }
  if (pct >= PP_RULES.firstTakePct) {
    return { signal: { action: 'reduce', severity: 'warning', message: '浮盈 ' + ppSigned(pct) + '% 命中第一档移动止盈' },
      decision: { action: 'partial', reduceRatio: PP_RULES.firstReduceRatio, confidence: 'medium',
        reasons: ['监控信号触发减仓，卖出研判按第一档比例出三成。'] } };
  }
  return { signal: { action: 'hold', severity: 'info', message: '浮盈 ' + ppSigned(pct) + '% 未触发任何档位' },
    decision: { action: 'hold', reduceRatio: null, confidence: 'medium', reasons: ['无信号，保持持有。'] } };
}

function ppNextSlot(acc) {
  const next = acc.cursor + 1;
  if (next > acc.slots.length - 1) {
    return { idx: acc.slots.length - 1, reused: true };
  }
  return { idx: next, reused: false };
}

function ppRunMonitor(acc) {
  if (acc.status === 'archived') return { blocked: '已归档账户不再执行模拟任务，历史只读。' };
  const slot = ppNextSlot(acc);
  const rep = ppReplay(acc);
  const out = { stamp: ppStamp(acc, slot.idx), filled: 0, rejected: 0, skipped: 0, degraded: [], reused: slot.reused, rows: [] };
  rep.positions.forEach((pos) => {
    const quote = ppQuote(acc, pos.code, slot.idx);
    if (quote.status !== 'ok') out.degraded.push({ code: pos.code, name: pos.name, status: quote.status });
    const decided = acc.variant === 'current_gate' ? ppDecideGate(acc, pos, quote) : ppDecideAI(acc, pos, quote);
    const action = acc.variant === 'current_gate' ? decided.decision.action : decided.action;
    const payload = acc.variant === 'current_gate'
      ? Object.assign({}, decided.decision, { signal: decided.signal })
      : decided;
    if (action === 'hold') { out.skipped += 1; return; }
    const side = action === 'add' ? 'buy' : 'sell';
    const origin = ppOrigin(acc, pos.code);
    const intent = {
      side: side, action: action, reduceRatio: payload.reduceRatio, allocationPct: payload.allocationPct,
      planId: pos.planId, label: ppIntentLabel(action, payload)
    };
    const res = ppExecute(acc, intent, quote, pos, rep.cash);
    const trace = ppDecisionTrace(acc, quote, payload);
    const reasons = payload.reasons || (payload.decision && payload.decision.reasons) || [];
    const ctx = ppAddContext(acc, {
      code: pos.code, d: ppSlot(acc, slot.idx).d, t: ppSlot(acc, slot.idx).t,
      stage: acc.variant === 'current_gate' ? 'monitor' : 'position_action',
      mode: acc.mode, factAsOf: quote.stamp, tools: trace.tools, web: trace.web,
      signal: payload.signal, decision: { action: action, reduceRatio: payload.reduceRatio,
        allocationPct: payload.allocationPct, confidence: payload.confidence, reasons: reasons,
        riskNote: payload.riskNote || '' }
    });
    const row = ppCommit(acc, {
      d: ctx.d, t: ctx.t, code: pos.code, side: side, action: action,
      price: res.status === 'filled' ? res.price : quote.price,
      shares: res.status === 'filled' ? res.shares : 0,
      status: res.status, reason: res.reason, intent: intent.label,
      contextId: ctx.id, planId: pos.planId, note: res.note || ''
    });
    if (res.status === 'filled') {
      out.filled += 1;
      ppApplyPlan(acc, pos.code, action, action === 'add' ? res.allocPct : null);
      ppAddAlert(acc, {
        code: pos.code, d: ctx.d, severity: action === 'exit' ? 'critical' : 'warning',
        source: acc.variant === 'current_gate' ? 'paper_sell' : 'paper_monitor', contextId: ctx.id,
        message: ppIntentLabel(action, payload) + '：' + String(reasons[0] || '').replace(/。$/, '') + '，已按 ' + row.price + ' '
          + (side === 'buy' ? '买入 ' : '卖出 ') + row.shares + ' 股'
      });
      if (side === 'sell') {
        ppAddReview(acc, {
          code: pos.code, d: ctx.d, execId: row.id,
          candidateId: origin ? origin.candidateId : null, scoreId: origin ? origin.scoreId : null,
          planId: row.planId, factAsOf: quote.stamp, gaps: [],
          summary: action === 'exit'
            ? pos.name + ' 本轮全额离场，成交价 ' + row.price + '，本轮已实现盈亏 ' + ppSigned(+(row.gross - row.fee - pos.avg * row.shares).toFixed(2)) + ' 元。'
            : pos.name + ' 减仓 ' + row.shares + ' 股，剩余 ' + (pos.shares - row.shares) + ' 股改用移动止损保护。',
          lesson: '减仓档位与可卖数量的换算需要按 T+1 校验，避免出现不足一手的拒绝。',
          auditReason: '', confidence: null,
          support: '', dissent: '', boundary: '',
          shadowNote: '收盘后的 AI 审核任务会自动处理这一条。'
        });
      }
    } else {
      out.rejected += 1;
      ppAddAlert(acc, {
        code: pos.code, d: ctx.d, severity: 'warning', source: 'paper_execution', contextId: ctx.id,
        message: '模拟执行已拒绝：' + ppLabel(res.reason) + (res.note ? '，' + res.note : '')
      });
    }
    out.rows.push(row);
  });
  if (out.degraded.length) {
    out.degraded.forEach((d) => {
      ppAddAlert(acc, {
        code: d.code, d: ppSlot(acc, slot.idx).d, severity: 'warning', source: 'paper_valuation', contextId: null,
        message: '模拟估值提示：' + d.name + '（' + d.code + '）' + (d.status === 'stale'
          ? '本时点未取到新行情，已用上一轮有效价格回填为参考行情，不用于成交。'
          : '本时点没有任何可用价格，模拟总资产显示为「模拟估值暂不完整」。')
      });
    });
  }
  acc.cursor = slot.idx;
  ppLogRun(acc, { at: out.stamp, kind: 'monitor', filled: out.filled, rejected: out.rejected, skipped: out.skipped });
  return out;
}

function ppRunIntents(acc) {
  if (acc.status === 'archived') return { blocked: '已归档账户不再执行模拟任务，历史只读。' };
  const idx = Math.min(acc.cursor, acc.slots.length - 1);
  const slot = ppSlot(acc, idx);
  const out = { stamp: ppStamp(acc, idx), filled: 0, rejected: 0, rows: [], skipped: 0, reused: false, degraded: [] };
  if (!acc.intents.length) {
    out.empty = '当前没有待执行的模拟意图，等下一轮候选池或研判产出意图后再补跑。';
    return out;
  }
  const pending = acc.intents.slice();
  acc.intents = [];
  pending.forEach((intent) => {
    const quote = ppQuote(acc, intent.code, idx);
    if (!quote) { out.skipped += 1; return; }
    if (quote.status !== 'ok') out.degraded.push({ code: intent.code, name: quote.name, status: quote.status });
    const rep = ppReplay(acc);
    const pos = rep.positions.filter((p) => p.code === intent.code)[0];
    const action = intent.action || (intent.side === 'buy' ? (pos ? 'add' : 'open') : 'reduce');
    const payload = Object.assign({}, intent, { action: action });
    const res = ppExecute(acc, {
      side: intent.side, action: action,
      allocationPct: intent.allocationPct, reduceRatio: intent.reduceRatio, planId: intent.planId
    }, quote, pos, rep.cash);
    const trace = ppDecisionTrace(acc, quote, payload);
    const reasons = intent.side === 'buy'
      ? ['候选池意图：目标仓位 ' + (intent.allocationPct == null ? '未给出' : intent.allocationPct + '%') + '，来源 ' + intent.from + '。']
      : ['持仓动作意图：减仓比例 ' + (intent.reduceRatio == null ? '模型未给出' : Math.round(intent.reduceRatio * 100) + '%') + '。'];
    const ctx = ppAddContext(acc, {
      code: intent.code, d: slot.d, t: slot.t, stage: 'research', mode: acc.mode,
      factAsOf: quote.stamp, tools: trace.tools, web: trace.web,
      rejected: res.status === 'filled' ? '' : res.reason,
      decision: { action: intent.side === 'buy' ? 'add' : 'reduce', allocationPct: intent.allocationPct,
        reduceRatio: intent.reduceRatio, confidence: res.status === 'filled' ? 'medium' : 'low',
        reasons: reasons, riskNote: res.note || '' }
    });
    const row = ppCommit(acc, {
      d: slot.d, t: slot.t, code: intent.code, side: intent.side,
      price: res.status === 'filled' ? res.price : quote.price,
      shares: res.status === 'filled' ? res.shares : 0,
      status: res.status, reason: res.reason,
      intent: intent.side === 'buy' ? 'AI 判定买入' + (intent.allocationPct == null ? '（比例缺失）' : ' ' + intent.allocationPct + '%')
        : 'AI 减仓' + (intent.reduceRatio == null ? '（比例缺失）' : ' ' + Math.round(intent.reduceRatio * 100) + '%'),
      contextId: ctx.id, planId: intent.planId, scoreId: intent.scoreId, candidateId: intent.candidateId,
      note: res.note || ''
    });
    if (res.status === 'filled') {
      out.filled += 1;
      ppApplyPlan(acc, intent.code, intent.side === 'buy' ? 'add' : 'reduce');
      if (intent.side === 'sell') {
        const origin = ppOrigin(acc, intent.code);
        ppAddReview(acc, {
          code: intent.code, d: slot.d, execId: row.id, planId: row.planId,
          scoreId: origin ? origin.scoreId : row.scoreId,
          candidateId: origin ? origin.candidateId : row.candidateId,
          factAsOf: quote.stamp, gaps: [],
          summary: row.name + ' 按意图减仓 ' + row.shares + ' 股。',
          lesson: '意图与成交要逐条对账，拒绝也必须留痕。', shadowNote: '收盘后的 AI 审核任务会自动处理这一条。'
        });
      }
      ppAddAlert(acc, {
        code: intent.code, d: slot.d, severity: 'info', source: 'paper_execution', contextId: ctx.id,
        message: '模拟' + (intent.side === 'buy' ? '买入' : '卖出') + '已成交：' + row.shares + ' 股 @' + row.price + '，' + reasons[0]
      });
    } else {
      out.rejected += 1;
      ppAddAlert(acc, {
        code: intent.code, d: slot.d, severity: 'warning', source: 'paper_execution', contextId: ctx.id,
        message: '模拟执行已拒绝：' + ppLabel(res.reason) + (res.note ? '，' + res.note : '')
      });
    }
    out.rows.push(row);
  });
  ppLogRun(acc, { at: out.stamp, kind: 'run', filled: out.filled, rejected: out.rejected, skipped: out.skipped });
  return out;
}

function ppRefreshQuotes(acc) {
  if (acc.status === 'archived') return { blocked: '已归档账户不再拉取行情，历史只读。' };
  const slot = ppNextSlot(acc);
  acc.cursor = slot.idx;
  const val = ppValuation(acc);
  const degraded = val.rows.filter((r) => r.quote.status !== 'ok');
  ppLogRun(acc, { at: ppStamp(acc, slot.idx), kind: 'quote', filled: 0, rejected: 0, skipped: degraded.length });
  return { stamp: ppStamp(acc, slot.idx), degraded: degraded, valuation: val, reused: slot.reused };
}

function ppAuditReview(acc, id) {
  const rv = acc.reviews.filter((r) => r.id === id)[0];
  if (!rv) return null;
  const derived = ['candidate_id', 'score_id', 'plan_id', 'trade_date', 'fact_as_of'].filter((key) => {
    const map = { candidate_id: 'candidateId', score_id: 'scoreId', plan_id: 'planId',
      trade_date: 'd', fact_as_of: 'factAsOf' };
    return rv[map[key]] == null || rv[map[key]] === '';
  }).map((key) => 'missing:' + key);
  rv.gaps = (rv.gaps || []).concat(derived).filter((g, i, arr) => arr.indexOf(g) === i);
  const gaps = rv.gaps;
  if (gaps.length) {
    rv.audit = 'fail';
    rv.auditReason = '事实闸门未通过：' + gaps.join('; ');
    rv.shadow = 'blocked';
    rv.shadowNote = '';
  } else {
    rv.audit = 'pass';
    rv.auditReason = rv.auditReason || '候选、评分、建仓计划来源齐全，交易日期与事实时点一致，未发现未来数据。';
    rv.shadow = 'pending';
    rv.shadowNote = '审核通过只允许进入影子验证，不代表正式规则已采纳。';
  }
  rv.auditMode = 'ai';
  rv.confidence = rv.confidence == null ? (rv.audit === 'pass' ? 78 : 45) : rv.confidence;
  return rv;
}

function ppManualReview(acc, id, verdict, reason) {
  const rv = acc.reviews.filter((r) => r.id === id)[0];
  if (!rv) return null;
  rv.audit = verdict;
  rv.auditMode = 'manual';
  rv.auditReason = '人工复审：' + reason;
  rv.shadow = verdict === 'pass' ? 'pending' : 'blocked';
  rv.shadowNote = verdict === 'pass' ? '人工复审覆盖 AI 结论，理由已留痕；仍是影子案例，不是正式规则。' : '';
  return rv;
}

function ppShadowStart(acc, id) {
  const rv = acc.reviews.filter((r) => r.id === id)[0];
  if (!rv || rv.shadow !== 'pending') return null;
  rv.shadow = 'active';
  rv.shadowNote = '影子验证中：只跟踪假设表现，不改动任何正式规则（rule_change 无新增）。';
  return rv;
}

function ppCreateAccount(payload) {
  const rows = ppData();
  const id = ppNextId('acc');
  const template = rows.filter((acc) => acc.id === 901)[0];
  const codes = ['601138', '300750', '600584'];
  const universe = {};
  codes.forEach((code) => { universe[code] = clone(template.universe[code]); });
  const acc = {
    id: id, name: payload.name, status: 'active', variant: payload.variant, mode: payload.mode,
    quoteSource: payload.mode === 'historical_replay' ? 'historical_snapshot' : 'tencent',
    initialCash: Number(payload.initialCash), createdAt: '2026-11-16',
    model: payload.model, ruleVersion: payload.ruleVersion, cursor: 0,
    schedule: { every: Number(payload.every) || PP_RULES.monitorMinutes,
      window: '交易日 09:30-11:30 / 13:00-15:00', next: '2026-11-17 09:33' },
    replayNote: payload.mode === 'historical_replay' ? '历史回放只用当日冻结事实：不回填今天的持仓、行情和知识库。' : '',
    slots: clone(template.slots), universe: universe,
    execs: [], plans: {}, contexts: [], alerts: [], reviews: [], runs: [],
    intents: codes.map((code) => ({
      code: code, side: 'buy', allocationPct: 10, candidateId: 'C-1116-' + code,
      scoreId: 5600 + codes.indexOf(code), planId: 880 + codes.indexOf(code),
      from: '候选池 11-16 批次 · 手动建仓意图'
    }))
  };
  rows.push(acc);
  state.ppAcc = id;
  state.ppView = 'current';
  state.ppTab = 'positions';
  state.ppPos = codes[0];
  return acc;
}

/* ---------- AI 模拟操盘：页面渲染 ---------- */
function ppSortedExecs(acc) {
  return acc.execs.slice().sort((a, b) => (b.d + b.t).localeCompare(a.d + a.t));
}
function ppSortedContexts(acc) {
  return acc.contexts.slice().sort((a, b) => (b.d + b.t).localeCompare(a.d + a.t));
}
function ppLastContext(acc, code) {
  return ppSortedContexts(acc).filter((c) => c.code === code)[0] || null;
}
function ppExecContext(acc, row) {
  return row.contextId ? acc.contexts.filter((c) => c.id === row.contextId)[0] || null : null;
}
function ppQuoteTag(q) {
  if (!q) return tag('无行情事实', 'mute');
  if (q.status === 'ok') return tag('行情正常', 'green');
  if (q.referenceOnly) return tag('参考行情 · 不用于成交', 'gold');
  if (q.status === 'suspended') return tag('标的停牌', 'mute');
  return tag('行情暂缺 · 估值不完整', 'red');
}
function ppMoneyHtml(v, unit) {
  if (v == null) return '<span class="dim">—</span>';
  return '<span class="mono">' + ppAmount(v) + '</span><span class="dim"> ' + (unit || '元') + '</span>';
}
function ppSideTag(row) {
  const buy = row.side === 'buy';
  return tag(ppLabel(buy ? 'buy' : 'sell') + (row.action ? ' · ' + ppLabel(row.action) : ''), buy ? 'red' : 'green');
}

function renderPaper() {
  ppData();
  const accounts = ppAccounts(state.ppView);
  const acc = ppAcc();
  const val = ppValuation(acc);
  const metrics = ppMetricHtml(acc, val);
  const banner = ppBannerHtml(acc, val);
  const chips = accounts.map((a) => {
    const v = ppValuation(a);
    return '<button class="cp-chip ' + (a.id === acc.id ? 'active' : '') + '" data-action="pp-account" data-acc="' + a.id + '">' +
      esc(a.name) + ' <span class="mono dim">' + a.id + '</span> ' +
      '<span class="mono ' + ppCls(v.pnl) + '">' + (v.pnl == null ? '估值暂不完整' : ppSigned(v.pnl, 0) + ' 元') + '</span></button>';
  }).join('');
  const views = [['current', '运行中/已暂停'], ['archived', '已归档']].map((v) =>
    '<button class="seg-item ' + (state.ppView === v[0] ? 'active' : '') + '" data-action="pp-view" data-view="' + v[0] + '">' + v[1] +
    '<span class="seg-count">' + ppAccounts(v[0]).length + '</span></button>').join('');
  const tabs = PP_TABS.map((t) => {
    const n = t[0] === 'positions' ? val.rows.length
      : t[0] === 'executions' ? acc.execs.length
      : t[0] === 'contexts' ? acc.contexts.length
      : t[0] === 'alerts' ? acc.alerts.length : acc.reviews.length;
    return '<button class="detail-tab ' + (state.ppTab === t[0] ? 'active' : '') + '" data-action="pp-tab" data-tab="' + t[0] + '">' +
      t[1] + ' ' + tag(String(n), 'mute') + '</button>';
  }).join('');
  const body = state.ppTab === 'positions' ? ppPositionsHtml(acc, val)
    : state.ppTab === 'executions' ? ppExecutionsHtml(acc, val)
    : state.ppTab === 'contexts' ? ppContextsHtml(acc)
    : state.ppTab === 'alerts' ? ppAlertsHtml(acc) : ppReviewsHtml(acc);

  return '<div class="page-head"><div>' +
      '<div class="page-title">AI 模拟操盘</div>' +
      '<div class="page-sub">AI 自己下单的隔离账本：买了什么、为什么买、赚亏多少、有没有正常跑。只写 paper 表，与你的真实持仓和券商账户完全无关。</div>' +
    '</div>' +
    '<div class="page-actions">' +
      '<button class="btn sm" data-action="pp-new">' + icon('plus', 'sm') + '新建模拟账户</button>' +
      '<button class="btn sm" data-action="pp-toggle">' + icon(acc.status === 'active' ? 'clock' : 'rotate', 'sm') +
        (acc.status === 'active' ? '暂停自动运行' : acc.status === 'paused' ? '继续自动运行' : '已归档 · 只读') + '</button>' +
      '<button class="btn sm" data-action="pp-quote"' + (acc.status === 'archived' ? ' disabled' : '') + '>' + icon('rotate', 'sm') + '刷新行情</button>' +
      '<button class="btn sm" data-action="pp-monitor"' + (acc.status === 'archived' ? ' disabled' : '') + '>' + icon('clock', 'sm') + '模拟巡检</button>' +
      '<button class="btn primary sm" data-action="pp-run"' + (acc.status === 'archived' || !acc.intents.length ? ' disabled' : '') + '>' +
        icon('agent', 'sm') + '立即补跑' + (acc.intents.length ? ' ' + tag(String(acc.intents.length), 'mute') : '') + '</button>' +
      '<button class="btn sm" data-action="pp-archive"' + (acc.status === 'archived' ? ' disabled' : '') + '>' + icon('ban', 'sm') + '归档账户</button>' +
    '</div></div>' +
    '<div class="cp-toolbar pp-bar"><div class="cp-chips">' + views + '</div>' +
      '<div class="cp-chips">' + chips + '</div>' +
      '<span class="spacer"></span>' +
      '<button class="btn link xs" data-nav="#/holdings">我的真实持仓 ' + icon('arrow', 'sm') + '</button></div>' +
    '<div class="cp-toolbar"><div class="detail-tabs pp-tabs">' + tabs + '</div></div>' +
    banner + metrics + ppFactsHtml(acc, val) +
    '<div class="pp-body">' + body + '</div>' +
    '<div class="cap-note" style="margin-top:14px">' + icon('info') +
      '<div>闭环：候选池 → AI 研判（研究取证留档）→ 模拟执行器（整手 / T+1 / 现金 / 费用 / 涨跌停）→ paper 账本与估值 → 模拟复盘 → AI 审核 → 影子验证。' +
      '<b>审核通过也不会改正式规则</b>，规则改动必须走<a class="btn link xs" data-nav="#/system/rules">规则审计</a>的人工门禁并留痕在 rule_change。</div></div>';
}

function ppBannerHtml(acc, val) {
  const lines = [];
  if (acc.status === 'archived') {
    lines.push({ tone: 'mute', text: '账户已归档（' + esc(acc.archivedAt || '') + '）：调度不再触发，历史成交、取证与复盘全部保留，页面只读。' });
    if (acc.archiveReason) lines.push({ tone: 'mute', text: '归档原因：' + esc(acc.archiveReason) });
  } else if (acc.status === 'paused') {
    lines.push({ tone: 'warn', text: '自动运行已暂停：调度不会再触发巡检与补跑，下面「模拟巡检 / 立即补跑」仍然可以手动打一轮。' });
  } else {
    lines.push({ tone: 'ok', text: '自动运行中：' + esc(acc.schedule.window) + '，每 ' + acc.schedule.every + ' 分钟一轮；下一轮 ' + esc(acc.schedule.next) + '。' });
  }
  if (acc.mode === 'historical_replay') {
    lines.push({ tone: 'info', text: esc(acc.replayNote || '历史回放只用当日冻结事实：不回填今天的持仓、行情和知识库。') });
  }
  if (val.quoteStatus === 'stale') {
    lines.push({ tone: 'warn', text: '行情已过期，仅供参考：本时点有标的没取到新行情，估值用上一轮有效价格回填，标签已改成「估算」。参考行情一律不能用来成交。' });
  } else if (val.quoteStatus === 'partial_or_unavailable') {
    lines.push({ tone: 'err', text: '模拟估值暂不完整：' + val.rows.filter((r) => r.price == null).map((r) => r.name).join('、') +
      ' 在本时点没有任何可用价格。系统不用成本价伪造市值，所以模拟市值、总资产和累计盈亏一起留空。' });
  }
  lines.push({ tone: 'proto', text: '静态原型说明：这一页只重算页面数据，不会真的下单，也不会连你的券商账户。行情、AI 结论和证据都来自脚本化的事实序列，点「刷新行情 / 模拟巡检 / 立即补跑」往前推一格。' });
  return '<div class="pp-banner">' + lines.map((l) =>
    '<div class="pp-banner-line ' + l.tone + '">' + (l.tone === 'proto' ? icon('info', 'sm') : icon('alert', 'sm')) + '<span>' + l.text + '</span></div>').join('') + '</div>';
}

function ppMetricHtml(acc, val) {
  const items = [
    { label: '模拟现金', value: ppAmount(val.rep.cash),
      sub: '初始 ' + ppAmount(Number(acc.initialCash)) + ' 元', tone: '' },
    { label: val.mvLabel, value: val.marketValue == null ? '暂不完整' : ppAmount(val.marketValue),
      sub: val.marketValue == null ? '有标的没有可用行情' : val.rows.length + ' 只模拟持仓', tone: val.marketValue == null ? 'err' : '' },
    { label: val.equityLabel, value: val.equity == null ? '暂不完整' : ppAmount(val.equity),
      sub: val.equity == null ? '拒绝用成本价伪造市值' : '现金 ' + ppAmount(val.rep.cash) + ' + 市值', tone: val.equity == null ? 'err' : 'info' },
    { label: '累计盈亏', value: val.pnl == null ? '—' : ppPct(val.pnlPct),
      sub: val.pnl == null ? '等行情齐了再算' : ppSigned(val.pnl, 0) + ' 元 · 已实现 ' + ppSigned(val.rep.realized, 0) + ' / 浮动 ' + ppSigned(val.unrealized, 0),
      tone: val.pnl == null ? '' : val.pnl > 0 ? 'up' : val.pnl < 0 ? 'down' : '' }
  ];
  return '<div class="metric-strip q4 pp-metrics">' + items.map((s) =>
    '<div class="metric"><div class="metric-label">' + esc(s.label) + '</div>' +
    '<div class="metric-value ' + s.tone + '">' + esc(s.value) + '</div>' +
    '<div class="metric-sub">' + esc(s.sub) + '</div></div>').join('') + '</div>';
}

function ppFactsHtml(acc, val) {
  const facts = [
    ['行情事实时点', val.factAsOf + '（第 ' + (Math.min(acc.cursor, acc.slots.length - 1) + 1) + '/' + acc.slots.length + ' 格）'],
    ['行情来源', ppLabel(acc.quoteSource) + (val.rows.some((r) => r.quote.source !== acc.quoteSource) ? ' · 本轮含回填' : '')],
    ['策略变体', ppLabel(acc.variant) + (acc.variant === 'candidate_pool' ? '：AI 决定加/减/清与幅度' : '：监控信号 → 卖出研判')],
    ['研判与执行版本', acc.model + ' · ' + acc.ruleVersion],
    ['调度节奏', '每 ' + acc.schedule.every + ' 分钟 · ' + acc.schedule.window],
    ['成交 / 拒绝', val.rep.filled + ' 笔已成交 · ' + val.rep.rejected + ' 笔被拒绝（拒绝全部留痕）']
  ];
  return '<div class="pp-facts">' + facts.map((f) =>
    '<div class="pp-fact"><span class="pp-fact-k">' + esc(f[0]) + '</span><span class="pp-fact-v">' + esc(f[1]) + '</span></div>').join('') +
    '<div class="pp-runlog">' + acc.runs.slice(0, 5).map((r) =>
      '<span class="pp-run"><b class="mono">' + esc(r.at) + '</b> ' +
      esc(r.kind === 'quote' ? '刷新行情' : r.kind === 'monitor' ? '模拟巡检' : r.kind === 'run' ? '立即补跑' : r.kind === 'review' ? '复盘审核' : '归档') +
      ' ' + (r.note ? esc(r.note) : '成交 ' + r.filled + ' / 拒绝 ' + r.rejected + ' / 跳过 ' + r.skipped) + '</span>').join('') + '</div></div>';
}

function ppPositionsHtml(acc, val) {
  const rows = val.rows;
  const sel = rows.filter((r) => r.code === state.ppPos)[0] || rows[0] || null;
  if (sel) state.ppPos = sel.code;
  return '<div class="cp-layout">' +
    '<div class="card cp-list-card">' +
      '<div class="rq-bar">' + (rows.length
        ? '<b>模拟持仓 ' + rows.length + ' 只</b><span class="dim">左键换标的；现价、浮动盈亏和 T+1 可卖都由成交回放算出</span>'
        : '<span class="dim">这个账户还没有模拟持仓，点「立即补跑」执行候选池意图就会建起来</span>') + '</div>' +
      '<div class="cp-list" id="pp-list">' +
        (rows.length ? rows.map((r) => ppPosRowHtml(acc, r)).join('')
          : '<div class="empty-list" style="margin:14px"><strong>没有模拟持仓</strong>新建账户后，「立即补跑」会按候选池意图下单；被拒绝的意图也会逐条留在模拟流水里。</div>') +
      '</div>' +
      '<div class="hd-list-foot"><span class="hint">' + esc(val.notice || '行情正常，估值口径与后端 account_view 一致') + '</span>' +
        '<span class="spacer"></span><span class="hint dim">事实时点 ' + esc(val.factAsOf) + '</span></div>' +
    '</div>' +
    '<div class="cp-detail" id="pp-detail">' + (sel ? ppPosDetailHtml(acc, sel, val)
      : '<div class="card"><div class="empty-list"><strong>选择一只模拟持仓</strong>这里看它的 AI 决策、取证证据、保护价和相关流水。</div></div>') + '</div>' +
  '</div>';
}

function ppPosRowHtml(acc, p) {
  const active = state.ppPos === p.code;
  return '<div class="cp-row pp-row' + (active ? ' active' : '') + '" role="button" tabindex="0" data-action="pp-pos" data-code="' + p.code + '">' +
    '<div class="cp-row-top">' +
      '<span class="hold-dot ' + (p.price == null ? 'err' : p.pnl != null && p.pnl < 0 ? 'warn' : 'ok') + '"></span>' +
      '<span class="cp-name">' + esc(p.name) + ' <span class="mono dim">' + p.code + '</span></span>' +
      '<span class="spacer"></span>' +
      '<span class="mono ' + ppCls(p.pnlPct) + '">' + (p.pnlPct == null ? '—' : ppPct(p.pnlPct)) + '</span>' +
    '</div>' +
    '<div class="cp-row-reason">' + esc(ppLastContext(acc, p.code) && ppLastContext(acc, p.code).decision
      ? ppLabel(ppLastContext(acc, p.code).decision.action) + '：' + (ppLastContext(acc, p.code).decision.reasons[0] || '')
      : '本时点没有 AI 动作，保持持有') + '</div>' +
    '<div class="hd-row-nums">' +
      '<span>现价 <b class="mono">' + (p.price == null ? '—' : p.price.toFixed(2)) + '</b></span>' +
      '<span>成本 <b class="mono">' + p.avg.toFixed(2) + '</b></span>' +
      '<span>持仓 <b class="mono">' + p.shares + '</b> / 可卖 <b class="mono">' + p.available + '</b></span>' +
      '<span>占比 <b class="mono">' + p.allocatedPct.toFixed(1) + '%</b></span>' +
    '</div>' +
    '<div class="cp-row-foot">' +
      '<span class="mono dim">' + (p.marketValue == null ? '市值待行情' : ppAmount(p.marketValue) + ' 元') + '</span>' +
      ppQuoteTag(p.quote) +
      (p.phase ? tag(ppLabel(p.phase), 'outline') : '') +
      '<span class="spacer"></span>' +
      '<span class="mono ' + ppCls(p.pnl) + '">' + (p.pnl == null ? '—' : ppSigned(p.pnl, 0) + ' 元') + '</span>' +
    '</div></div>';
}

function ppPosDetailHtml(acc, p, val) {
  const ctx = ppLastContext(acc, p.code);
  const execs = ppSortedExecs(acc).filter((r) => r.code === p.code).slice(0, 5);
  const alerts = acc.alerts.filter((a) => a.code === p.code).slice(0, 4);
  const guard = p.guard;
  const kline = candKlineHtml({ stock_code: p.code, stock_name: p.name, trade_date: val.rep.date, last: p.price || p.avg }, '本时点', true);
  return '<div class="card pp-detail-card">' +
    '<div class="cp-detail-head"><div>' +
      '<div class="cp-title">' + esc(p.name) + ' <span class="mono dim">' + p.code + '</span></div>' +
      '<div class="cp-sub">' + esc(p.theme || '未标注主线') + ' · 建仓日 ' + esc(p.openedAt) + ' · 事实时点 ' + esc(p.quote.stamp) + '</div>' +
      '<div class="detail-tags">' + ppQuoteTag(p.quote) + ' ' +
        (p.quote.referenceOnly ? tag('行情已过期，仅供参考', 'gold') : '') +
        (p.phase ? tag(ppLabel(p.phase), 'outline') : '') +
        tag('目标上限 ' + PP_RULES.maxAllocationPct + '%', 'mute') + '</div></div>' +
      '<div class="spacer"></div>' +
      '<div class="cp-acts">' +
        '<button class="btn sm" data-action="pp-kline" aria-expanded="' + state.ppKline + '">' + icon('chart', 'sm') + (state.ppKline ? '收起K线' : '看K线') + '</button>' +
        quoteUrls(p.code).map((q) => '<a class="btn link xs" href="' + q.url + '" target="_blank" rel="noopener noreferrer">' + esc(q.name) + ' ' + icon('external', 'sm') + '</a>').join('') +
      '</div></div>' +
    '<div class="pp-grid">' +
      ppCell('现价', p.price == null ? '—' : p.price.toFixed(2), p.quote.chgPct == null ? '' : ppPct(p.quote.chgPct), ppCls(p.quote.chgPct)) +
      ppCell('浮动盈亏', p.pnl == null ? '—' : ppSigned(p.pnl, 0) + ' 元', p.pnlPct == null ? '估值暂不完整' : ppPct(p.pnlPct), ppCls(p.pnlPct)) +
      ppCell('成本 / 股数', p.avg.toFixed(2), p.shares + ' 股（可卖 ' + p.available + '）', 'dim') +
      ppCell('持仓市值', p.marketValue == null ? '—' : ppAmount(p.marketValue) + ' 元', '占总资金 ' + p.allocatedPct.toFixed(1) + '%', 'dim') +
    '</div>' +
    '<div class="pp-guards">' + [
      ['硬止损 ' + PP_RULES.hardStopPct + '%', guard.stop.toFixed(2), p.distStop == null ? '待行情' : '距现价 ' + ppSigned(p.distStop, 1) + '%'],
      ['第一止盈 +' + PP_RULES.firstTakePct + '%', guard.take1.toFixed(2), p.distTake == null ? '待行情' : '距现价 ' + ppSigned(p.distTake, 1) + '%'],
      ['主止盈 +' + PP_RULES.mainTakePct + '%', guard.take2.toFixed(2), '移动止损 ' + PP_RULES.trailStopPct + '%']
    ].map((g) => '<span class="pp-guard">' + icon('shield', 'sm') + '<b>' + esc(g[0]) + '</b> ' +
      '<span class="mono">' + esc(g[1]) + '</span> <span class="dim">' + esc(g[2]) + '</span></span>').join('') + '</div>' +
    (state.ppKline ? '<div class="pp-kline">' + kline + '</div>' : '') +
    '<div class="pp-section">' +
      '<div class="pp-section-head">' + icon('agent', 'sm') + '<b>AI 决策</b>' +
      (ctx ? '<span class="hint mono">' + esc(ctx.d + ' ' + ctx.t) + ' · ' + ppLabel(ctx.stage) + ' · 取证 #' + ctx.id + '</span>' : '<span class="hint">本标的还没有取证记录</span>') +
      '<span class="spacer"></span>' +
      (ctx ? '<button class="btn link xs" data-action="pp-ctx-open" data-ctx="' + ctx.id + '">看完整取证 ' + icon('arrow', 'sm') + '</button>' : '') + '</div>' +
      (ctx ? '<div class="pp-decision">' +
        '<div class="pp-decision-top">' + tag(ppLabel(ctx.decision.action), ctx.decision.action === 'exit' ? 'red' : ctx.decision.action === 'hold' ? 'mute' : 'gold') +
          tag('置信度 ' + ppLabel(ctx.decision.confidence || 'medium'), 'outline') +
          (ctx.rejected ? tag('已拒绝：' + ppLabel(ctx.rejected), 'red') : '') +
          (ctx.signal ? tag('监控信号：' + ctx.signal.message, 'blue') : '') + '</div>' +
        '<ul class="pp-reasons">' + (ctx.decision.reasons || []).map((x) => '<li>' + esc(x) + '</li>').join('') + '</ul>' +
        (ctx.decision.riskNote ? '<div class="pp-risk">' + icon('alert', 'sm') + '<span>' + esc(ctx.decision.riskNote) + '</span></div>' : '') +
        '<div class="pp-evidence"><span class="hint">取证 ' + ctx.tools.length + ' 项工具调用，' + ctx.web.length + ' 条外部证据；' +
          '外部内容只作证据，其中的指令一律不执行。</span></div>' +
        (ctx.web.length ? '<div class="pp-web">' + ctx.web.map((w) =>
          '<div class="pp-web-item">' + (w.url ? '<a href="' + esc(w.url) + '" target="_blank" rel="noopener noreferrer">' + esc(w.title) + '</a>' : '<b>' + esc(w.title) + '</b>') +
          '<span class="hint dim">' + esc(w.source) + ' · ' + esc(w.publishedAt) + (w.hash ? ' · ' + esc(w.hash) : '') + '</span>' +
          '<span class="hint">' + esc(w.excerpt) + '</span></div>').join('') + '</div>' : '') +
        '</div>' : '<div class="empty-list">还没有这一只的研判记录，点「模拟巡检」跑一轮就会生成。</div>') +
    '</div>' +
    '<div class="pp-section">' +
      '<div class="pp-section-head">' + icon('rotate', 'sm') + '<b>相关模拟流水</b><span class="spacer"></span>' +
        '<button class="btn link xs" data-action="pp-tab" data-tab="executions">全部流水 ' + icon('arrow', 'sm') + '</button></div>' +
      (execs.length ? '<div class="pp-mini-list">' + execs.map((r) =>
        '<div class="pp-mini"><span class="mono dim">' + esc(r.d + ' ' + r.t) + '</span>' + ppSideTag(r) +
        '<span class="mono">' + (r.shares ? r.shares + ' 股 @ ' + r.price.toFixed(2) : '0 股') + '</span>' +
        '<span class="hint">' + esc(r.intent) + '</span><span class="spacer"></span>' +
        (r.status === 'filled' ? tag('已成交', 'green') : tag('已拒绝 · ' + ppLabel(r.reason), 'red')) + '</div>').join('') + '</div>'
        : '<div class="empty-list">还没有成交记录。</div>') +
    '</div>' +
    (alerts.length ? '<div class="pp-section"><div class="pp-section-head">' + icon('alert', 'sm') + '<b>相关模拟告警</b><span class="spacer"></span>' +
      '<button class="btn link xs" data-action="pp-tab" data-tab="alerts">全部告警 ' + icon('arrow', 'sm') + '</button></div>' +
      '<div class="pp-mini-list">' + alerts.map((a) =>
        '<div class="pp-mini"><span class="state ' + (a.severity === 'critical' ? 'bad' : a.severity === 'warning' ? 'todo' : 'done') + '"></span>' +
        '<span class="mono dim">' + esc(a.d) + '</span><span class="hint">' + esc(a.message) + '</span></div>').join('') + '</div></div>' : '') +
  '</div>';
}

function ppCell(label, value, sub, cls) {
  return '<div class="pp-cell"><div class="pp-cell-k">' + esc(label) + '</div>' +
    '<div class="pp-cell-v mono">' + esc(value) + '</div>' +
    '<div class="pp-cell-s ' + (cls || 'dim') + '">' + esc(sub) + '</div></div>';
}

const PP_FILTERS = [['', '全部'], ['filled', '已成交'], ['rejected', '已拒绝'], ['buy', '买入方向'], ['sell', '卖出方向']];

function ppExecutionsHtml(acc, val) {
  const all = ppSortedExecs(acc);
  const rows = all.filter((r) => !state.ppFilter
    || (state.ppFilter === 'buy' || state.ppFilter === 'sell' ? r.side === state.ppFilter : r.status === state.ppFilter));
  const counts = { filled: all.filter((r) => r.status === 'filled').length, rejected: all.length - all.filter((r) => r.status === 'filled').length };
  return '<div class="card">' +
    '<div class="card-title"><h3>模拟流水（' + all.length + '）</h3>' +
      '<span class="hint">每一笔都被回放成现金、成本、T+1 可卖和已实现盈亏；被拒绝的意图同样留痕</span>' +
      '<span class="spacer"></span>' +
      '<div class="cp-chips">' + PP_FILTERS.map((f) =>
        '<button class="cp-chip ' + (state.ppFilter === f[0] ? 'active' : '') + '" data-action="pp-filter" data-filter="' + f[0] + '">' + f[1] + '</button>').join('') + '</div></div>' +
    (rows.length ? '<div class="table-wrap"><table class="pp-table">' +
      '<thead><tr><th>事实时点</th><th>标的</th><th>方向</th><th>AI 意图</th><th>成交价</th><th>股数</th><th>金额</th><th>费用</th><th>结果</th><th>原因 / 说明</th><th>取证</th></tr></thead><tbody>' +
      rows.map((r) => '<tr class="' + (r.status === 'filled' ? '' : 'pp-row-rej') + '">' +
        '<td class="mono dim">' + esc(r.d + ' ' + r.t) + '</td>' +
        '<td><button class="btn link xs pp-link-name" data-action="pp-pos" data-code="' + r.code + '">' + esc(r.name) + '</button> <span class="mono dim">' + r.code + '</span></td>' +
        '<td>' + ppSideTag(r) + '</td>' +
        '<td class="hint">' + esc(r.intent || '—') + '</td>' +
        '<td class="mono">' + (r.price ? r.price.toFixed(2) : '—') + '</td>' +
        '<td class="mono">' + (r.shares || 0) + '</td>' +
        '<td class="mono">' + (r.gross ? ppAmount(r.gross) : '—') + '</td>' +
        '<td class="mono dim">' + (r.fee ? r.fee.toFixed(2) : '—') + '</td>' +
        '<td>' + (r.status === 'filled' ? tag('已成交', 'green') : tag('已拒绝', 'red')) + '</td>' +
        '<td class="hint">' + (r.reason ? tag(ppLabel(r.reason), 'gold') + ' ' : '') + esc(r.note || (r.status === 'filled' ? '滑点 ±5bp 已计入成交价' : '')) + '</td>' +
        '<td>' + (r.contextId ? '<button class="btn link xs" data-action="pp-ctx-open" data-ctx="' + r.contextId + '">#' + r.contextId + '</button>' : '<span class="dim">—</span>') + '</td>' +
      '</tr>').join('') + '</tbody></table></div>'
      : '<div class="empty-list" style="margin:16px">这个筛选下没有流水。</div>') +
    '<div class="hd-list-foot"><span class="hint">成交 ' + counts.filled + ' 笔 · 拒绝 ' + counts.rejected + ' 笔 · 已实现盈亏 ' +
      ppSigned(val.rep.realized, 2) + ' 元</span><span class="spacer"></span>' +
      '<span class="hint dim">费用口径：佣金万 3（最低 5 元）+ 过户费万 0.1，卖出再加印花税万 5</span></div>' +
  '</div>';
}

function ppContextsHtml(acc) {
  const rows = ppSortedContexts(acc);
  const openId = state.ppCtx != null ? state.ppCtx : (rows[0] ? rows[0].id : null);
  return '<div class="card">' +
    '<div class="card-title"><h3>研究取证（' + rows.length + '）</h3>' +
      '<span class="hint">每个模拟动作都要留下工具调用与证据；回放模式只用当日冻结快照</span>' +
      '<span class="spacer"></span>' +
      '<button class="btn sm" data-action="pp-research">' + icon('search', 'sm') + '手动研究取证</button></div>' +
    (rows.length ? '<div class="pp-ctx-list">' + rows.map((c) => ppCtxHtml(acc, c, c.id === openId)).join('') + '</div>'
      : '<div class="empty-list" style="margin:16px">还没有取证记录，点「模拟巡检」或「手动研究取证」生成。</div>') +
  '</div>';
}

function ppCtxHtml(acc, c, open) {
  const linked = acc.execs.filter((r) => r.contextId === c.id);
  return '<div class="pp-ctx' + (open ? ' open' : '') + '" id="pp-ctx-' + c.id + '">' +
    '<button class="pp-ctx-head" data-action="pp-ctx" data-ctx="' + c.id + '" aria-expanded="' + open + '">' +
      '<span class="mono dim">' + esc(c.d + ' ' + c.t) + '</span>' +
      '<span class="cp-name">' + esc((acc.universe[c.code] || {}).name || c.code) + ' <span class="mono dim">' + esc(c.code) + '</span></span>' +
      tag(ppLabel(c.stage), 'blue') + tag(ppLabel(c.mode), 'mute') +
      (c.rejected ? tag('闸门拒绝：' + ppLabel(c.rejected), 'red') : '') +
      (c.decision && c.decision.action ? tag('结论：' + ppLabel(c.decision.action), 'outline') : '') +
      '<span class="spacer"></span><span class="hint dim">#' + c.id + ' · 取证 ' + c.tools.length + ' 项' + (c.web.length ? ' · 外部证据 ' + c.web.length + ' 条' : '') + '</span>' +
      '<span class="icon sm">' + (open ? '▴' : '▾') + '</span></button>' +
    (open ? '<div class="pp-ctx-body">' +
      '<dl class="kv">' +
        '<dt>事实时点</dt><dd>' + esc(c.factAsOf || '未记录') + ' · 与决策时点一致才允许进入研判</dd>' +
        '<dt>工具轨迹</dt><dd><div class="pp-tools">' + c.tools.map((t) =>
          '<div class="pp-tool"><span class="state ' + (t.status === 'ok' ? 'done' : 'bad') + '"></span>' +
          '<b>' + esc(ppLabel(t.tool)) + '</b><span class="hint">' + esc(t.status === 'ok' ? t.summary : t.error) + '</span></div>').join('') + '</div></dd>' +
        '<dt>外部证据</dt><dd>' + (c.web.length ? c.web.map((w) =>
          '<div class="pp-web-item">' + (w.url ? '<a href="' + esc(w.url) + '" target="_blank" rel="noopener noreferrer">' + esc(w.title) + '</a>' : '<b>' + esc(w.title) + '</b>') +
          '<span class="hint dim">' + esc(w.source || '外部') + ' · ' + esc(w.publishedAt) + ' · 抓取哈希 ' + esc(w.hash || '—') + '</span>' +
          '<span class="hint">' + esc(w.excerpt) + '</span></div>').join('')
          : '<span class="dim">' + (acc.mode === 'historical_replay' ? '历史回放不联网，只用当日冻结快照。' : '本轮没有引用外部证据。') + '</span>') + '</dd>' +
        '<dt>研判结论</dt><dd>' + (c.signal ? '<div class="hint">监控信号：' + esc(c.signal.message) + '（' + ppLabel(c.signal.severity) + '）</div>' : '') +
          '<div class="pp-decision">' + '<div class="pp-decision-top">' +
            tag(ppLabel(c.decision.action), c.decision.action === 'exit' ? 'red' : c.decision.action === 'hold' ? 'mute' : 'gold') +
            tag('置信度 ' + ppLabel(c.decision.confidence || 'medium'), 'outline') +
            (c.decision.reduceRatio != null ? tag('减仓 ' + Math.round(c.decision.reduceRatio * 100) + '%', 'blue') : '') +
            (c.decision.allocationPct != null ? tag('目标 ' + c.decision.allocationPct + '%', 'blue') : '') + '</div>' +
            '<ul class="pp-reasons">' + (c.decision.reasons || []).map((x) => '<li>' + esc(x) + '</li>').join('') + '</ul>' +
            (c.decision.riskNote ? '<div class="pp-risk">' + icon('alert', 'sm') + '<span>' + esc(c.decision.riskNote) + '</span></div>' : '') + '</div></dd>' +
        '<dt>关联流水</dt><dd>' + (linked.length ? linked.map((r) =>
          '<div class="pp-mini"><span class="mono dim">' + esc(r.d + ' ' + r.t) + '</span>' + ppSideTag(r) +
          '<span class="mono">' + (r.shares ? r.shares + ' 股 @ ' + r.price.toFixed(2) : '0 股') + '</span>' +
          (r.status === 'filled' ? tag('已成交', 'green') : tag('已拒绝 · ' + ppLabel(r.reason), 'red')) + '</div>').join('')
          : '<span class="dim">这份取证没有产生成交（研判结论为不动，或被闸门拦下）</span>') + '</dd>' +
      '</dl>' +
      '<div class="cap-note" style="margin-top:12px">' + icon('info') +
        '<div>正式端把这条记录写进 paper_context（含 context_hash、tool_trace、source_refs），复盘和审核都从同一份冻结事实出发；' +
        '回放里任何晚于决策时点的字段都会被 future_data 闸门拒绝。</div></div>' +
      '</div>' : '') + '</div>';
}

function ppAlertsHtml(acc) {
  const rows = acc.alerts.slice().sort((a, b) => b.d.localeCompare(a.d));
  return '<div class="card">' +
    '<div class="card-title"><h3>模拟告警（' + rows.length + '）</h3>' +
      '<span class="hint">只报模拟盘自己的事：AI 动作、闸门拒绝、行情降级；与真实持仓的告警分开</span></div>' +
    (rows.length ? '<div class="pp-alert-list">' + rows.map((a) =>
      '<div class="pp-alert"><span class="state ' + (a.severity === 'critical' ? 'bad' : a.severity === 'warning' ? 'todo' : 'done') + '"></span>' +
      '<div class="pp-alert-main"><b>' + esc((acc.universe[a.code] || {}).name || a.code) + ' <span class="mono dim">' + esc(a.code) + '</span></b>' +
      '<div class="hint">' + esc(a.message) + '</div>' +
      '<span class="hint dim">' + esc(a.d) + ' · 来源 ' + esc(a.source) + '</span></div>' +
      '<span class="spacer"></span>' +
      '<button class="btn xs" data-action="pp-pos" data-code="' + esc(a.code) + '">定位标的</button>' +
      (a.contextId ? '<button class="btn link xs" data-action="pp-ctx-open" data-ctx="' + a.contextId + '">看取证 ' + icon('arrow', 'sm') + '</button>' : '') +
      '</div>').join('') + '</div>'
      : '<div class="empty-list" style="margin:16px">这个账户还没有模拟告警。</div>') +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') +
      '<div>这一页是模拟盘告警；你自己的持仓提醒在<a class="btn link xs" data-nav="#/alerts">告警日志</a>，两套来源分开记录，不会互相覆盖。</div></div>' +
  '</div>';
}

function ppReviewsHtml(acc) {
  const rows = acc.reviews.slice().sort((a, b) => b.d.localeCompare(a.d));
  return '<div class="card">' +
    '<div class="card-title"><h3>模拟复盘（' + rows.length + '）</h3>' +
      '<span class="hint">收盘后的审核任务逐条处理；「AI 审核通过」只是进入影子验证，不等于正式规则改动</span></div>' +
    (rows.length ? '<div class="pp-review-list">' + rows.map((r) => ppReviewHtml(acc, r)).join('') + '</div>'
      : '<div class="empty-list" style="margin:16px">还没有模拟复盘：模拟卖出成交后会自动排队一条待 AI 审核的复盘。</div>') +
  '</div>';
}

function ppReviewHtml(acc, r) {
  const stage = r.audit === 'pending' ? ['待AI审核', 'todo'] : r.audit === 'pass' ? ['AI审核通过', 'done'] : ['AI审核未通过', 'bad'];
  if (r.auditMode === 'manual' && r.audit !== 'pending') stage[0] = r.audit === 'pass' ? '人工复核通过' : '人工复核未通过';
  const form = state.ppForm && state.ppForm.kind === 'review' && state.ppForm.id === r.id;
  const exec = r.execId ? acc.execs.filter((x) => x.id === r.execId)[0] : null;
  return '<div class="pp-review' + (r.audit === 'pending' ? ' pending' : '') + '">' +
    '<div class="pp-review-head"><b>' + esc((acc.universe[r.code] || {}).name || r.code) + ' <span class="mono dim">' + esc(r.code) + '</span></b>' +
      '<span class="mono dim">' + esc(r.d) + '</span>' +
      tag(stage[0], stage[1] === 'done' ? 'green' : stage[1] === 'bad' ? 'red' : stage[1] === 'todo' ? 'gold' : 'mute') +
      (r.auditMode === 'manual' ? tag('人工覆盖 AI', 'outline') : '') +
      tag(ppShadowLabel(r.shadow), r.shadow === 'active' ? 'blue' : r.shadow === 'pending' ? 'gold' : r.shadow === 'blocked' ? 'red' : 'mute') +
      '<span class="spacer"></span>' +
      (exec ? '<button class="btn link xs" data-action="pp-ctx-open" data-ctx="' + (exec.contextId || '') + '">看这笔取证</button>' : '') +
      '</div>' +
    '<dl class="kv">' +
      '<dt>复盘结论</dt><dd>' + esc(r.summary) + '</dd>' +
      '<dt>可复用经验</dt><dd>' + esc(r.lesson) + '</dd>' +
      '<dt>事实闸门</dt><dd>' + (r.gaps && r.gaps.length
        ? r.gaps.map((g) => tag(g, 'red')).join(' ') + '<div class="hint">缺来源的事实不允许通过，这条永远进不了影子验证。</div>'
        : '<span class="hint">候选 / 评分 / 建仓计划 / 交易日期 / 事实时点都齐</span>') + '</dd>' +
      (r.auditReason ? '<dt>审核意见</dt><dd>' + esc(r.auditReason) +
        (r.confidence != null ? '<div class="hint dim">模型置信度 ' + r.confidence + '/100</div>' : '') + '</dd>' : '') +
      (r.support ? '<dt>支持观点</dt><dd>' + esc(r.support) + '</dd>' : '') +
      (r.dissent ? '<dt>反面观点</dt><dd>' + esc(r.dissent) + '</dd>' : '') +
      (r.boundary ? '<dt>适用边界</dt><dd>' + esc(r.boundary) + '</dd>' : '') +
      (r.shadowNote ? '<dt>影子验证</dt><dd>' + esc(r.shadowNote) + '</dd>' : '') +
    '</dl>' +
    (form ? '<div class="pp-inline-form">' +
      '<div class="pp-inline-row"><label class="radio"><input type="radio" name="pp-rv-verdict" value="pass"' + (state.ppForm.verdict === 'pass' ? ' checked' : '') + '><span>同意进入影子验证</span></label>' +
        '<label class="radio"><input type="radio" name="pp-rv-verdict" value="fail"' + (state.ppForm.verdict === 'fail' ? ' checked' : '') + '><span>驳回</span></label></div>' +
      '<textarea class="input" id="pp-rv-reason" rows="3" placeholder="人工复审理由（必填，会作为留痕写进复盘记录）">' + esc(state.ppForm.reason || '') + '</textarea>' +
      '<div class="rq-reject-acts"><button class="btn primary sm" data-action="pp-review-save" data-id="' + r.id + '">提交人工复审</button>' +
        '<button class="btn sm" data-action="pp-review-cancel">取消</button>' +
        '<span class="hint">人工复审可以覆盖 AI 结论，但必须写理由；覆盖后依然只进影子验证，正式规则改动要走规则审计。</span></div>' +
      '</div>'
      : '<div class="pp-review-acts">' +
        (r.audit === 'pending' ? '<button class="btn primary sm" data-action="pp-review-audit" data-id="' + r.id + '">' + icon('agent', 'sm') + 'AI 审核这一条</button>' : '') +
        '<button class="btn sm" data-action="pp-review-manual" data-id="' + r.id + '">人工复审</button>' +
        (r.shadow === 'pending' ? '<button class="btn sm" data-action="pp-review-shadow" data-id="' + r.id + '">送入影子验证</button>' : '') +
        '<span class="hint">模拟结论只作为参考案例与待验证假设，不自动改任何阈值。</span></div>') +
  '</div>';
}

/* ---------- AI 模拟操盘：抽屉表单 ---------- */
function ppReadForm(prefix) {
  const out = {};
  document.querySelectorAll('[id^="' + prefix + '-"]').forEach((el) => {
    out[el.id.replace(prefix + '-', '')] = el.type === 'checkbox' ? el.checked : el.value;
  });
  return out;
}

function ppNewFormHtml(v, errs) {
  const d = Object.assign({ name: '候选池自主加仓 · 12月', initialCash: '200000', variant: 'candidate_pool',
    mode: 'live_paper', model: 'action-v1 / qwen-max', ruleVersion: 'paper-execution-v1', every: '5' }, v || {});
  const f = (label, input) => '<label class="hd-field"><span>' + label + '</span>' + input + '</label>';
  return '<div class="hd-form in-drawer">' +
    '<div class="hd-form-title">新建模拟账户 <span class="hint">独立账本，不动真实持仓</span></div>' +
    '<div class="hd-form-grid">' +
      f('账户名称 *', '<input class="input" id="pp-n-name" value="' + esc(d.name) + '">') +
      f('初始资金（元）*', '<input class="input mono" id="pp-n-initialCash" type="number" min="10000" step="10000" value="' + esc(d.initialCash) + '">') +
      f('策略变体', '<select class="input" id="pp-n-variant">' +
        '<option value="candidate_pool"' + (d.variant === 'candidate_pool' ? ' selected' : '') + '>候选池自主加减仓（AI 决定动作与幅度）</option>' +
        '<option value="current_gate"' + (d.variant === 'current_gate' ? ' selected' : '') + '>现有门禁链路（监控信号 → 卖出研判）</option></select>') +
      f('运行模式', '<select class="input" id="pp-n-mode">' +
        '<option value="live_paper"' + (d.mode === 'live_paper' ? ' selected' : '') + '>实时模拟（用当前行情）</option>' +
        '<option value="historical_replay"' + (d.mode === 'historical_replay' ? ' selected' : '') + '>历史回放（只用冻结快照）</option></select>') +
      f('研判版本', '<input class="input mono" id="pp-n-model" value="' + esc(d.model) + '">') +
      f('执行规则版本', '<input class="input mono" id="pp-n-ruleVersion" value="' + esc(d.ruleVersion) + '">') +
      f('巡检间隔（分钟，≥5）', '<input class="input mono" id="pp-n-every" type="number" min="5" step="1" value="' + esc(d.every) + '">') +
    '</div>' +
    (errs && errs.length ? '<div class="hd-warns">' + errs.map((e) =>
      '<div class="hd-warn">' + icon('alert', 'sm') + esc(e) + '</div>').join('') + '</div>' : '') +
    '<div class="hd-form-acts"><button class="btn sm" data-action="close-drawer">取消</button><span class="spacer"></span>' +
      '<button class="btn primary sm" data-action="pp-new-save">校验并创建</button></div>' +
    '<div class="cap-note" style="margin-top:12px">' + icon('info') +
      '<div>新账户带 3 条候选池建仓意图，创建后点「立即补跑」就能看到成交与拒绝；执行器仍然只做整手、T+1、现金、费用和涨跌停换算，' +
      '不会碰券商接口。</div></div>' +
  '</div>';
}

function ppResearchFormHtml(v, errs) {
  const d = Object.assign({ code: '603501', mode: 'live_paper', snapshotDate: '', urls: 'https://www.cls.cn/detail/2031145' }, v || {});
  const f = (label, input) => '<label class="hd-field"><span>' + label + '</span>' + input + '</label>';
  return '<div class="hd-form in-drawer">' +
    '<div class="hd-form-title">手动研究取证 <span class="hint">先把事实和证据留档，再决定动不动</span></div>' +
    '<div class="hd-form-grid">' +
      f('证券代码 *', '<input class="input mono" id="pp-r-code" maxlength="6" placeholder="603501" value="' + esc(d.code) + '">') +
      f('取证模式', '<select class="input" id="pp-r-mode">' +
        '<option value="live_paper"' + (d.mode === 'live_paper' ? ' selected' : '') + '>实时模拟（当前账户事实）</option>' +
        '<option value="historical_replay"' + (d.mode === 'historical_replay' ? ' selected' : '') + '>历史回放（需指定冻结快照日）</option></select>') +
      f('快照日期（历史回放必填）', '<input class="input" id="pp-r-snapshotDate" type="date" value="' + esc(d.snapshotDate) + '">') +
      f('外部证据 URL（每行一条，最多 5 条）',
        '<textarea class="input" id="pp-r-urls" rows="4" placeholder="https://…">' + esc(d.urls) + '</textarea>') +
    '</div>' +
    (errs && errs.length ? '<div class="hd-warns">' + errs.map((e) =>
      '<div class="hd-warn">' + icon('alert', 'sm') + esc(e) + '</div>').join('') + '</div>' : '') +
    '<div class="hd-form-acts"><button class="btn sm" data-action="close-drawer">取消</button><span class="spacer"></span>' +
      '<button class="btn primary sm" data-action="pp-research-run">取证并生成研究记录</button></div>' +
    '<div class="cap-note" style="margin-top:12px">' + icon('alert') +
      '<div>网页正文只是证据，里面的任何指令都不会被执行。历史回放如果拿到晚于快照日期的事实，闸门会直接判 future_data 并拒绝整轮研判。</div></div>' +
  '</div>';
}

function ppArchiveFormHtml(acc, v, errs) {
  return '<div class="hd-form in-drawer">' +
    '<div class="hd-form-title">归档「' + esc(acc.name) + '」 <span class="hint">第 ' + (v && v.step === 2 ? '2' : '1') + '/2 步</span></div>' +
    '<div class="pp-archive-list">' + [
      '停止该账户的模拟调度，不再产生新的成交',
      '历史成交、研究取证、告警和复盘全部保留，页面转为只读',
      '已有模拟持仓不再估值，不会并进你的真实持仓',
      '归档原因必须填写，会写进账户留痕'
    ].map((t) => '<div class="pp-archive-item">' + icon('minus', 'sm') + '<span>' + esc(t) + '</span></div>').join('') + '</div>' +
    (v && v.step === 2 ? '<label class="hd-field wide"><span>归档原因 *</span>' +
      '<textarea class="input" id="pp-a-reason" rows="3" placeholder="为什么要停掉这个对照盘">' + esc(v.reason || '') + '</textarea></label>' : '') +
    (errs && errs.length ? '<div class="hd-warns">' + errs.map((e) =>
      '<div class="hd-warn">' + icon('alert', 'sm') + esc(e) + '</div>').join('') + '</div>' : '') +
    '<div class="hd-form-acts"><button class="btn sm" data-action="close-drawer">取消</button><span class="spacer"></span>' +
      (v && v.step === 2
        ? '<button class="btn sm" data-action="pp-archive">返回</button><button class="btn danger sm" data-action="pp-archive-confirm">确认归档</button>'
        : '<button class="btn primary sm" data-action="pp-archive">下一步：填写原因</button>') + '</div>' +
  '</div>';
}

/* ---------- AI 模拟操盘：就地操作分派 ---------- */
function ppRoundToast(acc, res, title) {
  if (res.blocked) { toast('账户已归档', res.blocked, 'warn'); return; }
  const detail = res.rows && res.rows.length
    ? res.rows.map((r) => (r.status === 'filled'
        ? r.name + ' ' + ppLabel(r.side) + ' ' + r.shares + ' 股 @' + r.price.toFixed(2)
        : r.name + ' 被拒：' + ppLabel(r.reason))).join('；')
    : '本轮没有任何标的需要动手';
  const degraded = (res.degraded || []).map((d) => d.name + '：' + (d.status === 'stale' ? '参考行情'
    : d.status === 'suspended' ? '停牌' : '价格不可用')).join('、');
  toast(title + ' · ' + res.stamp,
    (res.reused ? '行情序列已到最后一格，沿用收盘事实。' : '') +
    '成交 ' + res.filled + ' / 拒绝 ' + res.rejected + ' / 不动 ' + res.skipped
    + (degraded ? ' / 行情降级 ' + degraded : '') + ' · ' + detail +
    '。原型只重算页面数据，不会真的下单。',
    res.rejected || degraded ? 'warn' : 'ok');
}

function handlePaperAction(action, el) {
  const acc = ppAcc();

  if (action === 'pp-view') {
    state.ppView = el.dataset.view;
    state.ppForm = null;
    renderView();
    syncPaperHash();
  } else if (action === 'pp-account') {
    state.ppAcc = Number(el.dataset.acc);
    state.ppForm = null;
    state.ppCtx = null;
    const val = ppValuation(ppAcc());
    state.ppPos = val.rows.length ? val.rows[0].code : '';
    renderView();
    syncPaperHash();
  } else if (action === 'pp-tab') {
    state.ppTab = el.dataset.tab;
    state.ppForm = null;
    renderView();
    syncPaperHash();
  } else if (action === 'pp-pos') {
    state.ppPos = el.dataset.code;
    state.ppTab = 'positions';
    state.ppForm = null;
    renderView();
    syncPaperHash();
    const row = $('.pp-row[data-code="' + state.ppPos + '"]');
    if (row) row.scrollIntoView({ block: 'nearest' });
  } else if (action === 'pp-kline') {
    state.ppKline = !state.ppKline;
    renderView();
  } else if (action === 'pp-filter') {
    state.ppFilter = el.dataset.filter;
    renderView();
    syncPaperHash();
  } else if (action === 'pp-ctx') {
    state.ppCtx = state.ppCtx === Number(el.dataset.ctx) ? null : Number(el.dataset.ctx);
    renderView();
    syncPaperHash();
  } else if (action === 'pp-ctx-open') {
    const id = Number(el.dataset.ctx);
    if (!id) { toast('这份记录没有取证编号', '执行器直接按意图拒绝，未生成研究记录。', 'info'); return; }
    state.ppTab = 'contexts';
    state.ppCtx = id;
    renderView();
    syncPaperHash();
    const node = document.getElementById('pp-ctx-' + id);
    if (node) node.scrollIntoView({ block: 'center' });
  } else if (action === 'pp-quote') {
    const res = ppRefreshQuotes(acc);
    if (res.blocked) { toast('账户已归档', res.blocked, 'warn'); return; }
    const val = ppValuation(acc);
    toast('行情已刷新 · ' + res.stamp,
      (res.reused ? '已是本序列最后一格（收盘快照），价格不再变化。' : '') +
      (res.degraded.length
        ? res.degraded.map((r) => r.name + '：' + (r.quote.referenceOnly ? '参考行情，估值用上一轮价格回填，不能用于成交' : '没有任何可用价格，总资产改显示「模拟估值暂不完整」')).join('；')
        : '全部标的取到新鲜行情。') +
      '当前口径：' + val.equityLabel + ' ' + (val.equity == null ? '暂不完整' : ppAmount(val.equity) + ' 元') + '。',
      res.degraded.length ? 'warn' : 'ok');
    renderView();
    syncPaperHash();
  } else if (action === 'pp-monitor') {
    const res = ppRunMonitor(acc);
    ppRoundToast(acc, res, '模拟巡检');
    renderView();
    syncPaperHash();
  } else if (action === 'pp-run') {
    const res = ppRunIntents(acc);
    if (res.blocked) { toast('账户已归档', res.blocked, 'warn'); return; }
    if (res.empty) { toast('没有待执行意图', res.empty, 'info'); renderView(); return; }
    ppRoundToast(acc, res, '立即补跑');
    renderView();
    syncPaperHash();
  } else if (action === 'pp-toggle') {
    if (acc.status === 'archived') { toast('已归档', '归档账户不能再变成运行中，请新建一个模拟账户。', 'warn'); return; }
    acc.status = acc.status === 'active' ? 'paused' : 'active';
    ppLogRun(acc, { at: ppStamp(acc, acc.cursor), kind: acc.status === 'active' ? 'monitor' : 'monitor',
      filled: 0, rejected: 0, skipped: 0, note: acc.status === 'active' ? '手动恢复自动运行' : '手动暂停自动运行' });
    renderView();
    toast(acc.status === 'active' ? '自动运行已恢复' : '自动运行已暂停',
      acc.status === 'active'
        ? '调度恢复：' + acc.schedule.window + '，每 ' + acc.schedule.every + ' 分钟一轮。'
        : '调度已摘掉，历史与模拟持仓保留；页面里的「模拟巡检 / 立即补跑」仍然可以手动打一轮。',
      acc.status === 'active' ? 'ok' : 'warn');
  } else if (action === 'pp-new') {
    state.ppForm = { kind: 'new' };
    openDrawer('pp-new');
  } else if (action === 'pp-new-save') {
    const v = ppReadForm('pp-n');
    const errs = [];
    if (!String(v.name || '').trim()) errs.push('账户名称不能为空');
    if (!(Number(v.initialCash) >= 10000)) errs.push('初始资金至少 1 万元，否则连一手都算不出来');
    if (!(Number(v.every) >= 5)) errs.push('巡检间隔最少 5 分钟，后端拒绝更密的 cron');
    if (!String(v.model || '').trim() || !String(v.ruleVersion || '').trim()) errs.push('研判版本与执行规则版本必须留档，不能留空');
    if (errs.length) {
      state.ppForm = Object.assign({ kind: 'new' }, v, { errs: errs });
      openDrawer('pp-new');
      toast('还没通过校验', errs[0], 'err');
      return;
    }
    const created = ppCreateAccount(v);
    state.ppForm = null;
    closeDrawer();
    renderView();
    syncPaperHash();
    toast('模拟账户已创建 · ' + created.id,
      created.name + '：初始 ' + ppAmount(Number(created.initialCash)) + ' 元，' + ppLabel(created.variant) + '，' +
      ppLabel(created.mode) + '。已带 3 条候选池建仓意图，点「立即补跑」就会按整手、T+1、现金和费用换算成交或拒绝。', 'ok');
  } else if (action === 'pp-research') {
    state.ppForm = { kind: 'research', code: state.ppPos || '603501', mode: acc.mode, snapshotDate: '', urls: '' };
    openDrawer('pp-research');
  } else if (action === 'pp-research-run') {
    const v = ppReadForm('pp-r');
    const errs = [];
    const urls = String(v.urls || '').split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
    if (!/^\d{6}$/.test(String(v.code || ''))) errs.push('证券代码必须是 6 位数字');
    if (urls.length > 5) errs.push('外部证据最多 5 条，先挑最相关的');
    if (urls.some((u) => !/^https?:\/\/.+/i.test(u))) errs.push('每条证据都要是完整 http(s) 链接');
    if (v.mode === 'historical_replay' && !/^\d{4}-\d{2}-\d{2}$/.test(String(v.snapshotDate || ''))) {
      errs.push('历史回放必须指定冻结快照日期，避免回填今天的行情');
    }
    const code = String(v.code || '');
    if (!errs.length && !acc.universe[code]) {
      acc.universe[code] = { name: '自定义标的 ' + code, prevClose: 20, series: [20.10, 20.40, 20.80, 20.60, 20.90, 21.20, 21.00] };
    }
    if (errs.length) {
      state.ppForm = Object.assign({ kind: 'research' }, v, { errs: errs });
      openDrawer('pp-research');
      toast('取证条件不足', errs[0], 'err');
      return;
    }
    const idx = Math.min(acc.cursor, acc.slots.length - 1);
    const quote = ppQuote(acc, code, idx);
    const future = v.mode === 'historical_replay' && String(v.snapshotDate) > ppSlot(acc, idx).d;
    const trace = ppDecisionTrace(acc, quote, {}, v.mode);
    trace.tools = trace.tools.concat(urls.map((u, i) => ({
      tool: 'paper_web.search', status: 'ok', summary: '证据 ' + (i + 1) + '：' + u.slice(0, 46)
    })));
    trace.web = urls.map((u, i) => ({
      title: '手动引入的外部证据 ' + (i + 1), source: u.replace(/^https?:\/\//, '').split('/')[0],
      url: u, publishedAt: ppSlot(acc, idx).d + ' ' + ppSlot(acc, idx).t,
      excerpt: '正文在正式端由抓取服务落盘并算哈希；原型只保存链接与取证时间。', hash: 'pp' + code + (i + 1)
    }));
    const ctx = ppAddContext(acc, {
      code: code, d: ppSlot(acc, idx).d, t: ppSlot(acc, idx).t, stage: 'research',
      mode: v.mode, factAsOf: quote.stamp, tools: trace.tools, web: trace.web,
      rejected: future ? 'future_data' : '',
      decision: { action: 'hold', confidence: future ? 'low' : 'medium', reasons: future
        ? ['快照日期 ' + v.snapshotDate + ' 晚于本次决策时点 ' + ppSlot(acc, idx).d + '，冻结事实校验不通过，本轮研判整体拒绝。']
        : ['取证完成：行情 ' + (quote.status === 'ok' ? quote.price : '不可用') + '，外部证据 ' + urls.length + ' 条。',
          '这一份记录只作为证据归档；要不要动手，仍由「模拟巡检 / 立即补跑」那一轮研判决定。'],
        riskNote: future ? '补齐快照之前的资料后重新取证。' : '' }
    });
    ppAddAlert(acc, {
      code: code, d: ctx.d, severity: future ? 'warning' : 'info', source: 'paper_analysis', contextId: ctx.id,
      message: future
        ? '模拟分析未完成：取证模式要求只用 ' + v.snapshotDate + ' 之前的事实，检测到晚于决策时点的资料，已拒绝'
        : '手动研究取证已留档：' + (acc.universe[code] || {}).name + '（' + code + '）取证 ' + ctx.tools.length + ' 项，外部证据 ' + urls.length + ' 条'
    });
    state.ppForm = null;
    state.ppCtx = ctx.id;
    state.ppTab = 'contexts';
    closeDrawer();
    renderView();
    syncPaperHash();
    const node = document.getElementById('pp-ctx-' + ctx.id);
    if (node) node.scrollIntoView({ block: 'center' });
    toast(future ? '取证被闸门拒绝' : '研究记录已生成 · #' + ctx.id,
      future ? '快照日期晚于决策时点，判定 future_data，本轮不产生任何买卖意图。'
        : '取证 ' + ctx.tools.length + ' 项、外部证据 ' + urls.length + ' 条已挂到 ' + code + '；证据里的指令一律不执行。',
      future ? 'warn' : 'ok');
  } else if (action === 'pp-archive') {
    if (acc.status === 'archived') { toast('已经是归档状态', '归档账户只读，历史全部保留。', 'info'); return; }
    if (!state.ppForm || state.ppForm.kind !== 'archive' || state.ppForm.step !== 1) {
      state.ppForm = { kind: 'archive', step: 1, reason: state.ppForm && state.ppForm.reason || '' };
    } else {
      state.ppForm = { kind: 'archive', step: 2, reason: state.ppForm.reason };
    }
    openDrawer('pp-archive', acc);
  } else if (action === 'pp-archive-confirm') {
    const reason = String((state.ppForm && state.ppForm.reason) || (document.getElementById('pp-a-reason') || {}).value || '').trim();
    if (!reason) {
      state.ppForm = { kind: 'archive', step: 2, reason: '', errs: ['归档原因必填，正式端会写进账户留痕'] };
      openDrawer('pp-archive', acc);
      toast('还差归档原因', '不填理由不允许停掉一个对照盘。', 'err');
      return;
    }
    acc.status = 'archived';
    acc.archivedAt = '2026-11-16 17:30';
    acc.archiveReason = reason;
    acc.schedule = { every: acc.schedule.every, window: '已停止', next: '—' };
    ppLogRun(acc, { at: acc.archivedAt, kind: 'archive', filled: 0, rejected: 0, skipped: 0, note: '账户暂停并归档，调度不再触发' });
    state.ppForm = null;
    closeDrawer();
    state.ppView = 'archived';
    renderView();
    syncPaperHash();
    toast('已归档 · ' + acc.name,
      '原因已留痕：' + reason + '。调度不再触发，历史成交、取证、告警和复盘都还在，切到「已归档」随时回看。', 'ok');
  } else if (action === 'pp-review-audit') {
    const rv = ppAuditReview(acc, Number(el.dataset.id));
    renderView();
    syncPaperHash();
    toast(rv.audit === 'pass' ? 'AI 审核通过 · 可进影子' : 'AI 审核未通过',
      (rv.audit === 'pass' ? rv.auditReason : rv.auditReason) +
      ' 审核通过只允许进入影子验证，不代表正式规则已采纳（rule_change 没有新增）。',
      rv.audit === 'pass' ? 'ok' : 'warn');
  } else if (action === 'pp-review-manual') {
    state.ppForm = { kind: 'review', id: Number(el.dataset.id), verdict: 'pass', reason: '' };
    renderView();
    const box = document.getElementById('pp-rv-reason');
    if (box) box.focus();
  } else if (action === 'pp-review-cancel') {
    state.ppForm = null;
    renderView();
  } else if (action === 'pp-review-save') {
    const id = Number(el.dataset.id);
    const form = state.ppForm || {};
    const reason = String(form.reason || '').trim();
    if (!reason) {
      state.ppForm = Object.assign({}, form, { errs: ['人工复审必须写理由'] });
      renderView();
      toast('理由不能为空', '人工复审会覆盖 AI 结论，理由就是这条链路的留痕。', 'err');
      return;
    }
    ppManualReview(acc, id, form.verdict || 'pass', reason);
    state.ppForm = null;
    renderView();
    syncPaperHash();
    toast('人工复审已提交', '结论：' + (form.verdict === 'fail' ? '人工复核未通过' : '人工复核通过') +
      '。理由按「人工复审：…」原样留痕；即便覆盖 AI 的未通过结论，也仍然只进影子验证，不改正式规则。', 'ok');
  } else if (action === 'pp-review-shadow') {
    const rv = ppShadowStart(acc, Number(el.dataset.id));
    renderView();
    syncPaperHash();
    toast('已进入影子验证', '只在影子链路上跟踪这条假设的表现，正式阈值一个数字都没动；要变成规则仍需走规则审计的人工门禁。', 'info');
  } else if (action === 'pp-form-keep') {
    return;
  }
}

function syncPaperHash() {
  if (state.route !== '#/paper') return;
  let next = '#/paper?view=' + state.ppView + '&acc=' + state.ppAcc + '&tab=' + state.ppTab + '&pos=' + state.ppPos;
  if (state.ppFilter) next += '&filter=' + state.ppFilter;
  if (state.ppCtx != null) next += '&ctx=' + state.ppCtx;
  if (location.hash !== next) history.replaceState(null, '', next);
}

/* ================= 市场研判（#/market-intel） ================= */
/* 事实底座 = 全板块日快照（后端 sector_daily_snapshot，工作日 15:35 落库，rank_no 即当日板块涨幅名次）。
   原型带 8 个交易日的 top5 名单 + 14 个交易日的 top10 明细；C'/D'/E' 三层判定按后端同一套公式在浏览器现算，
   页面所有百分比都是这套公式 + 这张表算出来的，改表里的数字，结论会跟着变。 */
const MI_OLD_TOP5 = [
  ['2026-10-22', ['白酒', '煤炭开采', '光伏设备', '人形机器人', '银行']],
  ['2026-10-23', ['军工电子', '稀土永磁', 'CPO光模块', 'AI应用', '低空经济']],
  ['2026-10-26', ['稀土永磁', '煤炭开采', '存储芯片', '光伏设备', 'AI应用']],
  ['2026-10-27', ['白酒', '煤炭开采', '银行', '液冷服务器', '军工电子']],
  ['2026-10-28', ['银行', '固态电池', '白酒', 'CPO光模块', '低空经济']],
  ['2026-10-29', ['固态电池', '光伏设备', '算力租赁', '煤炭开采', '创新药']],
  ['2026-10-30', ['稀土永磁', '军工电子', '存储芯片', 'AI应用', '液冷服务器']],
  ['2026-11-02', ['创新药', '固态电池', 'CPO光模块', '银行', '低空经济']]
];
/* [板块, 涨幅%, 量比, 板块内上涨家数]，数组顺序即 rank_no */
const MI_DAILY = [
  ['2026-11-03', [['液冷服务器', 3.1, 2.0, 24], ['存储芯片', 2.6, 1.9, 28], ['CPO光模块', 2.4, 1.8, 33], ['人形机器人', 1.6, 1.3, 46], ['低空经济', 1.4, 1.2, 19], ['AI应用', 1.1, 1.1, 52], ['军工电子', 0.8, 0.9, 30], ['创新药', 0.6, 0.8, 40], ['光伏设备', 0.4, 0.9, 27], ['固态电池', 0.2, 0.8, 44]]],
  ['2026-11-04', [['存储芯片', 2.8, 1.7, 30], ['CPO光模块', 2.2, 1.6, 35], ['AI应用', 1.9, 1.5, 56], ['固态电池', 1.7, 1.4, 47], ['光伏设备', 1.2, 1.1, 29], ['液冷服务器', 0.9, 1.0, 23], ['人形机器人', 0.7, 0.9, 45], ['半导体设备', 0.5, 0.9, 38], ['低空经济', 0.3, 0.8, 18], ['军工电子', 0.1, 0.7, 29]]],
  ['2026-11-05', [['CPO光模块', 3.3, 2.2, 37], ['存储芯片', 1.8, 1.3, 31], ['液冷服务器', 1.6, 1.2, 25], ['半导体设备', 1.4, 1.3, 41], ['人形机器人', 1.2, 1.1, 44], ['AI应用', 0.9, 1.0, 54], ['固态电池', 0.7, 0.9, 46], ['军工电子', 0.5, 0.8, 30], ['光伏设备', 0.3, 0.8, 28], ['创新药', 0.1, 0.7, 39]]],
  ['2026-11-06', [['固态电池', 3.4, 2.1, 52], ['创新药', 2.5, 1.6, 43], ['人形机器人', 2.1, 1.5, 47], ['军工电子', 1.7, 1.2, 32], ['稀土永磁', 1.5, 1.3, 24], ['白酒', 1.2, 1.1, 15], ['煤炭开采', 1.0, 1.0, 12], ['CPO光模块', 0.6, 0.9, 36], ['低空经济', 0.4, 0.9, 19], ['光伏设备', 0.2, 0.8, 27]]],
  ['2026-11-09', [['创新药', 2.7, 1.8, 45], ['固态电池', 2.2, 1.6, 50], ['半导体设备', 1.9, 1.5, 40], ['存储芯片', 1.6, 1.4, 29], ['白酒', 1.3, 1.1, 14], ['稀土永磁', 0.8, 0.9, 23], ['军工电子', 0.6, 0.9, 31], ['AI应用', 0.4, 0.8, 53], ['人形机器人', 0.2, 0.8, 44], ['液冷服务器', -0.5, 0.7, 22]]],
  ['2026-11-10', [['半导体设备', 2.9, 1.9, 42], ['存储芯片', 2.4, 1.7, 31], ['创新药', 1.4, 1.2, 44], ['人形机器人', 0.9, 1.0, 45], ['液冷服务器', 0.8, 0.9, 26], ['AI应用', 0.7, 0.9, 54], ['CPO光模块', 0.5, 0.9, 35], ['固态电池', 0.2, 0.8, 48], ['低空经济', 0.1, 0.8, 18], ['煤炭开采', -0.3, 0.7, 11]]],
  ['2026-11-11', [['半导体设备', 2.2, 1.6, 43], ['CPO光模块', 3.0, 2.3, 36], ['人形机器人', 1.4, 1.2, 46], ['固态电池', 1.1, 1.1, 49], ['存储芯片', 0.8, 1.0, 33], ['创新药', 0.5, 0.9, 43], ['液冷服务器', 0.3, 0.9, 25], ['军工电子', -0.2, 0.7, 29], ['稀土永磁', -0.3, 0.8, 22], ['光伏设备', -0.4, 0.7, 26]]],
  ['2026-11-12', [['AI应用', 2.4, 1.8, 60], ['CPO光模块', 2.6, 2.0, 38], ['液冷服务器', 2.7, 2.1, 25], ['创新药', 1.3, 1.2, 42], ['固态电池', 0.9, 1.0, 47], ['半导体设备', 0.6, 0.9, 40], ['人形机器人', -0.2, 0.8, 44], ['稀土永磁', -0.4, 0.7, 21], ['军工电子', -0.6, 0.7, 28], ['算力租赁', -0.7, 0.9, 13]]],
  ['2026-11-13', [['CPO光模块', 2.9, 2.1, 40], ['液冷服务器', 2.3, 1.9, 26], ['算力租赁', 2.2, 2.0, 15], ['存储芯片', 1.5, 1.6, 34], ['AI应用', 1.2, 1.5, 57], ['半导体设备', 0.5, 0.9, 39], ['创新药', 0.2, 0.8, 41], ['人形机器人', 0.1, 0.8, 43], ['低空经济', -0.3, 0.8, 20], ['固态电池', -0.4, 0.7, 46]]],
  ['2026-11-16', [['CPO光模块', 3.4, 1.5, 43], ['液冷服务器', 2.8, 1.4, 28], ['算力租赁', 2.5, 1.6, 17], ['存储芯片', 1.4, 1.3, 36], ['AI应用', 1.1, 1.2, 55], ['半导体设备', 0.6, 0.9, 40], ['创新药', 0.3, 0.8, 41], ['人形机器人', 0.1, 0.8, 43], ['军工电子', -0.2, 0.7, 28], ['光伏设备', -0.5, 0.7, 25]]],
  ['2026-11-17', [['CPO光模块', 4.1, 2.6, 46], ['人形机器人', 2.4, 1.9, 47], ['光伏设备', 1.8, 1.8, 31], ['军工电子', 1.5, 1.7, 32], ['固态电池', 1.2, 1.6, 49], ['液冷服务器', 0.4, 1.0, 27], ['半导体设备', 0.2, 0.9, 40], ['存储芯片', 0.1, 0.9, 34], ['AI应用', -0.3, 0.8, 54], ['低空经济', -0.6, 0.7, 19]]],
  ['2026-11-18', [['CPO光模块', 3.6, 2.4, 44], ['液冷服务器', 3.0, 2.2, 30], ['半导体设备', 2.7, 1.9, 43], ['存储芯片', 2.1, 1.8, 36], ['AI应用', 1.6, 1.7, 56], ['算力租赁', 0.9, 1.1, 18], ['创新药', 0.4, 0.8, 42], ['人形机器人', 0.1, 0.8, 43], ['稀土永磁', -0.5, 0.7, 21], ['光伏设备', -0.9, 0.7, 26]]],
  ['2026-11-19', [['CPO光模块', 2.7, 1.6, 42], ['液冷服务器', 2.5, 1.5, 30], ['算力租赁', 2.3, 1.7, 19], ['存储芯片', 1.9, 1.4, 35], ['AI应用', 1.7, 1.3, 55], ['半导体设备', 0.8, 0.9, 40], ['人形机器人', 0.5, 0.8, 42], ['军工电子', 0.3, 0.8, 29], ['固态电池', 0.1, 0.7, 47], ['创新药', -0.2, 0.7, 46]]],
  ['2026-11-20', [['液冷服务器', 2.2, 1.5, 32], ['军工电子', 1.6, 1.3, 31], ['创新药', 1.1, 1.2, 46], ['白酒', 0.9, 1.1, 16], ['银行', 0.7, 1.0, 12], ['CPO光模块', -2.4, 1.4, 21], ['算力租赁', -1.8, 1.2, 11], ['存储芯片', -1.5, 1.1, 24], ['AI应用', -1.2, 1.0, 38], ['半导体设备', -0.9, 0.9, 31]]]
];
/* 60 日箱位（真实来自 fetch_board_box_positions）：原型按「最新值 + 全窗口线性走势」种子，
   越靠近窗口起点越偏离最新值；只用当日 top10 的板块。 */
const MI_BOX_LATEST = {
  'CPO光模块': 0.92, '液冷服务器': 0.88, '算力租赁': 0.79, '存储芯片': 0.74, '半导体设备': 0.61,
  'AI应用': 0.55, '人形机器人': 0.48, '固态电池': 0.42, '创新药': 0.51, '军工电子': 0.33,
  '稀土永磁': 0.45, '低空经济': 0.38, '光伏设备': 0.22, '白酒': 0.28, '煤炭开采': 0.35, '银行': 0.62
};
const MI_BOX_SLOPE = {
  'CPO光模块': 0.42, '液冷服务器': 0.36, '算力租赁': 0.45, '存储芯片': 0.20, '半导体设备': 0.14,
  'AI应用': 0.05, '人形机器人': -0.04, '固态电池': -0.10, '创新药': 0.02, '军工电子': -0.08,
  '稀土永磁': 0.12, '低空经济': -0.06, '光伏设备': -0.14, '白酒': -0.12, '煤炭开采': -0.10, '银行': 0.08
};
/* 箱位取数超时降级：后端线程 30s 未返回就按「缺失」处理，不阻塞主结果（sector_forward_view._fetch_boxes） */
const MI_BOX_MISSING = { date: '2026-11-19', sectors: ['液冷服务器'], note: '东财板块箱位接口 30s 未返回，本轮按缺失处理' };
const MI_WINDOW_LIMIT = 60;

/* 板块启动归因（sector_launch_reason）：AI 只写「为什么启动」，置信度按证据链/时间匹配/产业传导/资金验证算出来。 */
const MI_LAUNCH = {
  '2026-11-19': [
    {
      sector: 'CPO光模块', tags: '订单验证,算力资本开支,持续', days: 4, confidence: 0.82,
      text: '北美四家云厂商在 11 月财报电话会把 2027 年资本开支指引整体上修，1.6T 光模块出货指引由每季度 30 万只上调到 45 万只；' +
        '国内两家头部模组厂在手订单已排到 2027Q1，龙头 Q3 合同负债环比 +38%，属于业绩能兑现的产业逻辑而非纯情绪。' +
        '板块已连续 8 个交易日排在涨幅前五，量比 1.6 仍有增量资金，但 60 日箱位 0.92 已在历史高位，追高性价比下降。',
      chain: [
        { key: '云厂商资本开支指引', source: '公司公告', text: '四家云厂商 2027 年 capex 指引合计上修 18%，1.6T 出货指引 +50%。' },
        { key: '龙头合同负债', source: '财报', text: '中际旭创 Q3 合同负债环比 +38%，预收款项指向 2027Q1 交付。' },
        { key: '板块资金', source: '盘面数据', text: '连续 8 日 top5，量比 1.6，主力净流入 3 日累计 21.4 亿。' }
      ],
      causal: [
        { layer: '需求端', claim: '海外云厂商资本开支上修 → 光模块出货量预期上修', level: 'L1', align: '同周', cause: 'lead' },
        { layer: '供给端', claim: '1.6T 良率爬坡，头部厂商独占产能', level: 'L2', align: '滞后 2 周', cause: 'lead' },
        { layer: '盘面', claim: '板块涨幅榜连续居前、量能未衰减', level: 'L3', align: '同日', cause: 'post_move_explanation' }
      ],
      transmission: '云厂商 capex → 光模块整机 → 光器件/光芯片 → 高速连接器 → 液冷配套（同一批资金沿着链条向后传导）',
      capital: { main_net_in_3d: '21.4 亿', north_bound: '沪股通增持 4.2 亿', margin: '融资余额 5 日 +6.1%', turnover: '换手率 4.8%（近 60 日 92 分位）' },
      falsify: {
        t1: '次日板块跌出涨幅前十，或龙头缩量阴线（量比 <1）',
        t3: '3 日内北美云厂商下调指引 / 龙头公告订单延期',
        t5: '5 日累计涨幅转负且箱位仍 >0.9（高位滞涨=出货）',
        triggered: false
      },
      cap_reason: '有 L1 产业证据 + 资金验证，箱位过高扣 0.08'
    },
    {
      sector: '液冷服务器', tags: '渗透率,政策,持续', days: 3, confidence: 0.58,
      text: '工信部新建数据中心 PUE 要求收紧到 1.15，风冷方案无法满足，液冷渗透率从 14% 提到 30% 的预期在多家卖方报告中出现；' +
        '但落地订单集中在两家整机厂，板块内多数标的收入占比不足 10%，业绩弹性还没验证。箱位 0.88 偏高，属于「逻辑对、位置不便宜」。',
      chain: [
        { key: 'PUE 政策窗口', source: '政策文件', text: '新建大型数据中心 PUE ≤1.15，2027 年起执行。' },
        { key: '卖方渗透率预测', source: '研究报告', text: '液冷渗透率 2026 14% → 2027 30%（预测值，未落订单）。' }
      ],
      causal: [
        { layer: '政策端', claim: 'PUE 强制约束 → 液冷从可选变必选', level: 'L2', align: '同月', cause: 'lead' },
        { layer: '业绩端', claim: '板块标的液冷收入占比普遍 <10%，弹性未验证', level: 'L3', align: '缺失', cause: 'unusable_rumor' }
      ],
      transmission: '政策约束 → 数据中心改造 → 液冷整机 → 冷板/管路 → 冷却液',
      capital: { main_net_in_3d: '6.8 亿', north_bound: '无明显变化', margin: '融资余额 5 日 +1.2%', turnover: '换手率 3.1%' },
      falsify: { t1: '次日跌出前十且量比 <1.2', t3: '龙头没有新增中标公示', t5: '板块 5 日累计转负', triggered: false },
      cap_reason: '只有政策与预测证据，缺 L1 订单与资金确认，扣到中等档'
    },
    {
      sector: '算力租赁', tags: '情绪,传闻,emotion_only', days: 1, confidence: 0.36,
      text: '市场传某算力租赁商拿到新的大模型厂商长单，公司公告只写「正在洽谈」，未披露金额与期限；板块 3 日涨幅 12% 主要由游资席位推动。' +
        '这一条只有情绪与传闻，没有可回指的硬证据，不作为主线延续的依据。',
      chain: [
        { key: '长单传闻', source: '媒体报道', text: '未获公司公告确认，公告仅称「正在洽谈」。' }
      ],
      causal: [
        { layer: '消息端', claim: '传闻级长单 → 收入预期上修', level: 'L3', align: '缺失', cause: 'unusable_rumor' }
      ],
      transmission: '',
      capital: null,
      falsify: { t1: '公告澄清无此订单', t3: '游资席位退出龙虎榜', t5: '板块跌出前二十', triggered: true },
      cap_reason: '传闻未证实 + 反证条件已触发，置信度封顶 0.45'
    }
  ],
  '2026-11-18': [
    {
      sector: 'CPO光模块', tags: '订单验证,算力资本开支,持续', days: 4, confidence: 0.80,
      text: '云厂商资本开支上修的逻辑继续发酵，龙头当日 +3.6%、量比 2.4，板块连续 7 日 top5；' +
        '当天外围题材（稀土、低空）大量挤进涨幅榜前五，top5 换手率升到 0.8，说明增量资金开始在外围打游击，主线内部反而没有新资金接力。',
      chain: [
        { key: '云厂商资本开支指引', source: '公司公告', text: '2027 capex 合计上修 18%。' },
        { key: '外围题材挤榜', source: '盘面数据', text: '当日 top5 有 3 个是一日游题材。' }
      ],
      causal: [
        { layer: '需求端', claim: '海外 capex 上修 → 出货预期上修', level: 'L1', align: '同周', cause: 'lead' },
        { layer: '资金面', claim: '外围打板资金分流，主线增量不足', level: 'L3', align: '同日', cause: 'post_move_explanation' }
      ],
      transmission: '云厂商 capex → 光模块整机 → 光器件 → 连接器',
      capital: { main_net_in_3d: '14.1 亿', north_bound: '沪股通增持 1.8 亿', margin: '融资余额 5 日 +3.4%', turnover: '换手率 5.2%' },
      falsify: { t1: '次日龙头缩量阴线', t3: 'capex 指引被下调', t5: '5 日累计涨幅转负', triggered: false },
      cap_reason: '有 L1 证据 + 资金验证'
    },
    {
      sector: '稀土永磁', tags: '情绪,传闻,emotion_only', days: 1, confidence: 0.30,
      text: '出口管制相关消息带来单日脉冲，板块内多数标的没有业绩关联；量比 2.2 但上涨家数只有 22 家，属于资金短打。',
      chain: [{ key: '出口管制消息', source: '媒体报道', text: '消息未涉及具体标的与收入口径。' }],
      causal: [{ layer: '消息端', claim: '管制预期 → 涨价预期', level: 'L3', align: '同日', cause: 'unusable_rumor' }],
      transmission: '', capital: null,
      falsify: { t1: '次日跌出前十', t3: '无后续政策文件', t5: '5 日累计转负', triggered: false },
      cap_reason: '只有消息，没有产业传导'
    }
  ],
  '2026-11-17': [
    {
      sector: 'CPO光模块', tags: '订单验证,算力资本开支,持续', days: 3, confidence: 0.80,
      text: '龙头当日 +4.1% 创 60 日新高，量比 2.6；北美 capex 上修 + 国内 1.6T 良率爬坡两条证据都还在，' +
        '但涨幅已进入加速段，追高风险与延续概率同时抬高。',
      chain: [
        { key: '云厂商资本开支指引', source: '公司公告', text: '2027 capex 合计上修 18%。' },
        { key: '1.6T 良率', source: '产业链调研', text: '头部厂商良率过 70%，产能独占。' }
      ],
      causal: [
        { layer: '需求端', claim: 'capex 上修 → 出货预期上修', level: 'L1', align: '同周', cause: 'lead' },
        { layer: '供给端', claim: '良率爬坡 → 头部独占', level: 'L2', align: '滞后 2 周', cause: 'lead' }
      ],
      transmission: '云厂商 capex → 光模块整机 → 光器件/光芯片',
      capital: { main_net_in_3d: '18.9 亿', north_bound: '增持 2.6 亿', margin: '融资余额 5 日 +4.8%', turnover: '换手率 4.6%' },
      falsify: { t1: '次日缩量阴线', t3: '指引下调', t5: '5 日累计转负', triggered: false },
      cap_reason: '需求 + 供给双证据，资金确认完整'
    },
    {
      sector: '半导体设备', tags: '国产替代,招标', days: 2, confidence: 0.50,
      text: '两存储厂发布设备招标公告，国产化比例要求提高；金额尚未披露，按历史中标结构估算板块收入弹性 3-5%。',
      chain: [{ key: '设备招标公告', source: '公告', text: '招标清单已挂网，金额未定。' }],
      causal: [{ layer: '需求端', claim: '招标 → 国产设备订单', level: 'L2', align: '同月', cause: 'lead' }],
      transmission: '存储厂扩产 → 前道设备 → 零部件', capital: { main_net_in_3d: '4.2 亿', turnover: '换手率 2.4%' },
      falsify: { t1: '次日跌出前十', t3: '中标结果无国产厂商', t5: '5 日累计转负', triggered: false },
      cap_reason: '有招标事实但金额未定，中等档'
    }
  ],
  '2026-11-16': [
    {
      sector: 'CPO光模块', tags: '订单验证,持续', days: 3, confidence: 0.78,
      text: '周末海外云厂商财报落地，2027 资本开支指引上修，板块当日 +3.4% 重回涨幅第一，连续 5 日 top5。',
      chain: [{ key: '云厂商财报', source: '公司公告', text: 'capex 指引上修 18%。' }],
      causal: [{ layer: '需求端', claim: 'capex 上修 → 出货预期上修', level: 'L1', align: '同周', cause: 'lead' }],
      transmission: '云厂商 capex → 光模块整机 → 光器件', capital: { main_net_in_3d: '12.6 亿', turnover: '换手率 4.1%' },
      falsify: { t1: '次日跌出前十', t3: '指引被下调', t5: '5 日累计转负', triggered: false },
      cap_reason: 'L1 公告证据 + 资金净流入'
    },
    {
      sector: '液冷服务器', tags: '渗透率,政策', days: 2, confidence: 0.55,
      text: 'PUE 政策窗口叠加数据中心改造招标信息，板块 +2.8%，但收入弹性还没在报表里体现。',
      chain: [{ key: 'PUE 政策', source: '政策文件', text: '新建数据中心 PUE ≤1.15。' }],
      causal: [{ layer: '政策端', claim: 'PUE 约束 → 液冷必选化', level: 'L2', align: '同月', cause: 'lead' }],
      transmission: '政策 → 数据中心改造 → 液冷整机', capital: null,
      falsify: { t1: '次日跌出前十', t3: '无新增中标', t5: '5 日累计转负', triggered: false },
      cap_reason: '政策证据有，资金验证缺失'
    },
    {
      sector: '算力租赁', tags: '情绪', days: 1, confidence: 0.40,
      text: '跟随主线上涨，自身没有新增订单证据，属于主线扩散。',
      chain: [{ key: '跟随主线', source: '盘面数据', text: '板块上涨但缺少独立催化。' }],
      causal: [{ layer: '盘面', claim: '主线扩散 → 补涨', level: 'L3', align: '同日', cause: 'post_move_explanation' }],
      transmission: '', capital: null,
      falsify: { t1: '次日跌出前十', t3: '主线退潮则同步退潮', t5: '5 日累计转负', triggered: false },
      cap_reason: '只有盘面跟随，无产业证据'
    }
  ],
  '2026-11-13': [
    {
      sector: 'CPO光模块', tags: '订单验证,持续', days: 3, confidence: 0.76,
      text: '海外大厂下单传闻 + 卖方上调出货量预测，板块当日 +2.9% 重回第一；公告层面还没有正式合同，证据等级比 11-16 那一轮低一档。',
      chain: [{ key: '下单传闻', source: '媒体报道', text: '卖方报告称头部厂商获追加订单。' }],
      causal: [{ layer: '需求端', claim: '追加订单 → 出货上修', level: 'L2', align: '同周', cause: 'lead' }],
      transmission: '云厂商 → 光模块整机 → 光器件', capital: { main_net_in_3d: '8.4 亿', turnover: '换手率 3.8%' },
      falsify: { t1: '次日跌出前十', t3: '无公告确认', t5: '5 日累计转负', triggered: false },
      cap_reason: '报告级证据，未见公告'
    },
    {
      sector: '液冷服务器', tags: '渗透率', days: 2, confidence: 0.55,
      text: 'PUE 政策预期驱动的补涨，量比 1.8 但上涨家数只有 26 家，集中在两只整机股。',
      chain: [{ key: 'PUE 政策', source: '政策文件', text: 'PUE ≤1.15。' }],
      causal: [{ layer: '政策端', claim: 'PUE → 液冷改造', level: 'L2', align: '同月', cause: 'lead' }],
      transmission: '政策 → 改造需求 → 液冷整机', capital: null,
      falsify: { t1: '次日跌出前十', t3: '无中标', t5: '5 日累计转负', triggered: false },
      cap_reason: '集中度高，缺资金验证'
    }
  ]
};
/* top10 之外的「下一个风口」候选（sector_next_hot，15:50 跑）：父板块归因能否迁移过来是关键 */
const MI_NEXT_HOT = {
  '2026-11-20': [
    { sector: '军工电子', rank: 11, hot: 71, days: 4, conf: 0.44, trig: { missing: false, parent: 0.61, dist: '2 跳', logic: '航发订单 → 机载电子 → 连接器与电源模块', must: '下周两型新品定型公告；板块上涨家数需 >40' } },
    { sector: '低空经济', rank: 12, hot: 68, days: 3, conf: 0.31, trig: { missing: true, parent: null, dist: '未知', logic: '空域试点扩容，但没有可回指的产业订单证据', must: '试点城市名单落地 + 龙头公告 eVTOL 配套收入' } },
    { sector: '光伏设备', rank: 13, hot: 55, days: 2, conf: 0.26, trig: { missing: true, parent: 0.38, dist: '3 跳', logic: '硅料限价传闻 → 组件排产回升，链条过长', must: '排产数据连续两周环比转正' } }
  ],
  '2026-11-19': [
    { sector: '算力租赁', rank: 9, hot: 74, days: 3, conf: 0.36, trig: { missing: false, parent: 0.82, dist: '1 跳', logic: '光模块订单上修 → 机柜交付 → 算力租赁上架率', must: '龙头公告新增长单；否则按情绪票处理' } },
    { sector: '创新药', rank: 14, hot: 52, days: 2, conf: 0.40, trig: { missing: false, parent: 0.51, dist: '无关', logic: '与算力主线无传导关系，独立行情', must: '海外授权首付款到账公告' } }
  ]
};
/* 多窗口规律（sector_rotation_pattern.analyze_patterns 的口径） */
const MI_PATTERNS = {
  '3d': { days: 3, rotation_cycle: 1.8, lifecycle_avg_streak: 2.4, switch_frequency: 0.62, volume_breakout_continuation: 0.41, mainline: ['CPO光模块'], top_slopes: [{ s: 'CPO光模块', v: 3.1 }, { s: '液冷服务器', v: 2.4 }, { s: '算力租赁', v: 1.9 }] },
  '10d': { days: 10, rotation_cycle: 3.6, lifecycle_avg_streak: 5.2, switch_frequency: 0.38, volume_breakout_continuation: 0.55, mainline: ['CPO光模块', '存储芯片'], top_slopes: [{ s: 'CPO光模块', v: 2.6 }, { s: '液冷服务器', v: 2.1 }, { s: '半导体设备', v: 1.4 }] },
  '20d': { days: 20, rotation_cycle: 5.4, lifecycle_avg_streak: 7.8, switch_frequency: 0.27, volume_breakout_continuation: 0.48, mainline: ['CPO光模块', '液冷服务器'], top_slopes: [{ s: 'CPO光模块', v: 2.2 }, { s: '存储芯片', v: 1.3 }, { s: '创新药', v: 0.9 }] },
  '60d': { days: 60, rotation_cycle: 9.2, lifecycle_avg_streak: 11.6, switch_frequency: 0.18, volume_breakout_continuation: 0.44, mainline: ['CPO光模块'], top_slopes: [{ s: 'CPO光模块', v: 1.7 }, { s: 'AI应用', v: 0.8 }, { s: '银行', v: 0.6 }] }
};
/* 模块自检（/api/market/diagnostics）：7 张表 + 5 个定时任务的最新状态 */
const MI_DIAG = {
  tables: {
    sector_daily: { latest_date: '2026-11-20', row_count: 90, last_error: '' },
    sector_rotation: { latest_date: '2026-11-19', row_count: 5, last_error: '' },
    sector_launch_reason: { latest_date: '2026-11-19', row_count: 3, last_error: '' },
    sector_regime_forecast: { latest_date: '2026-11-19', row_count: 1, last_error: '' },
    sector_forward_forecast: { latest_date: '2026-11-19', row_count: 30, last_error: '' },
    sector_forecast_verify: { latest_date: '2026-11-16', row_count: 3, last_error: '' },
    sector_next_hot: { latest_date: '2026-11-20', row_count: 3, last_error: '' }
  },
  jobs: {
    sector_daily: { last_run_at: '2026-11-20 15:35:04', last_status: 'ok', last_error: '' },
    sector_regime: { last_run_at: '2026-11-20 15:40:37', last_status: 'failed', last_error: '数据源超时：fetch_board_box_positions 30s 未返回，C\' 结构判定中断' },
    sector_forward: { last_run_at: '2026-11-19 15:45:02', last_status: 'ok', last_error: '' },
    sector_forecast_verify: { last_run_at: '2026-11-20 16:05:11', last_status: 'ok', last_error: '' },
    sector_next_hot: { last_run_at: '2026-11-20 15:50:06', last_status: 'ok', last_error: '' }
  }
};
/* AI 市场研判记录（market_intel 表，工作日 16:20 跑）：只存 AI 写的文字字段，量能信号由快照现算 */
const MI_INTEL = {
  '2026-11-19': {
    phase: '主线加速后转分歧：龙头还在，外围开始散', risk: '中性',
    summary: '算力链仍是唯一抱团方向，但 11-18 起 top5 换手率升到 0.8，增量资金在外围打游击；结构没坏，位置已高，节奏比方向重要。',
    conflict: '矛盾点一：龙头订单证据仍然成立（L1 公告 + 合同负债），但 60 日箱位 0.92 已到历史 95 分位，延续概率和追高风险同时抬高。\n' +
      '矛盾点二：主线内部资金没有新增，涨幅靠估值扩张；外围题材（稀土、低空、固态）单日冲进 top5 又单日退出，说明打板资金在分流而不是接力。\n' +
      '矛盾点三：液冷与算力租赁一个缺订单验证、一个只有传闻长单，却跟着主线一起涨——真主线和伪扩散目前混在同一个涨幅榜里，只有拆到个股报表层才分得开。\n' +
      '这两个月最有效的做法是：只在主线里做已经证明业绩的环节，不碰跟随性补涨。',
    structure: { attack: 'CPO光模块（订单证据最硬，但位置最高，只做已证明业绩的龙头环节）', relay: '半导体设备（招标公告，箱位 0.61 还在中位）', fade: '算力租赁（传闻驱动，反证条件已触发）' },
    quality: '主线量能成色尚可但边际递减：CPO 量比从 11-17 的 2.6 降到 1.6，板块上涨家数从 46 家降到 42 家，是「缩量新高」的形态。',
    box: {
      'CPO光模块': '60 日箱位 92%：主升初期早已过去，现在是高位放量滞涨的风险区；但只要量比不塌到 1 以下，就不能直接判定出货。',
      '液冷服务器': '60 日箱位 88%：位置高但资金验证缺失（融资余额几乎没动），更像存量博弈的补涨。',
      '半导体设备': '60 日箱位 61%：唯一还在中位、且有招标公告的方向，是主线扩散的第一站。',
      '算力租赁': '60 日箱位 79%：反证条件已触发（公告未确认订单），按一日游处理，不作为延续依据。'
    },
    stocks: [
      { name: '中际旭创', code: '300308', chg: 4.2, vol: 1.9, box: 94, verdict: '加速后段' },
      { name: '新易盛', code: '300502', chg: 3.1, vol: 1.7, box: 91, verdict: '真强' },
      { name: '天孚通信', code: '300399', chg: 2.4, vol: 1.2, box: 96, verdict: '放量滞涨' },
      { name: '北方华创', code: '002371', chg: 2.8, vol: 1.6, box: 63, verdict: '真强' },
      { name: '英维克', code: '002837', chg: 1.1, vol: 0.9, box: 87, verdict: '假强' }
    ],
    watch: {
      '主线龙头量能': 'CPO 量比跌破 1.2 或收阴线 → 加速转分歧确认，减配高位环节',
      '外围一日游': '稀土/低空跌出前十 → 说明只是单日脉冲，不必跟进',
      '半导体设备': '招标公告是否落地成中标 → 落地则作为主线接力方向',
      '算力租赁': '是否有正式订单公告 → 没有就按情绪票处理，不参与',
      '两市成交额': '跌破 1.6 万亿则主线容错率下降，降低仓位上限'
    },
    meaning: '不追高位的加速段，等一次缩量回踩；接力方向看箱位还在中位的半导体设备；跟随性补涨（算力租赁）不作为建仓理由。',
    raw_extra: { board_volume_ratio_available: true, breadth: '上涨家数 2871 / 下跌 1904，非涨停口径', sample_size: '全板块 90 个' }
  },
  '2026-11-18': {
    phase: '主线高位加速，外围开始抢席位', risk: '进取',
    summary: '龙头 +3.6% 继续新高，但当日 top5 里出现了三个一日游题材；结构仍是主线，风险在位置。',
    conflict: '矛盾点一：主线证据仍然成立，箱位已 90%+。\n矛盾点二：top5 换手 0.8，抱团板块只剩龙头一个。\n处理方式：主线仓位不加仓，外围不参与。',
    structure: { attack: 'CPO光模块', relay: '创新药（独立逻辑，海外授权）', fade: '稀土永磁（消息脉冲）' },
    quality: '放量新高：龙头量比 2.4，板块上涨家数 44 家，成色比 11-17 略降。',
    box: { 'CPO光模块': '箱位 91%：加速段特征，回踩不破 10 日线可持有。', '稀土永磁': '箱位 45%：低位脉冲，没有产业传导。' },
    stocks: [
      { name: '中际旭创', code: '300308', chg: 5.1, vol: 2.4, box: 92, verdict: '加速后段' },
      { name: '新易盛', code: '300502', chg: 3.8, vol: 2.1, box: 89, verdict: '真强' },
      { name: '天孚通信', code: '300399', chg: 1.2, vol: 1.1, box: 94, verdict: '放量滞涨' }
    ],
    watch: { '龙头是否缩量': '量比 <1.5 视为加速段结束', '外围题材持续性': '稀土次日跌出前十即证伪' },
    meaning: '持有主线，不加仓；新开仓只考虑箱位中位以下的接力方向。',
    raw_extra: { board_volume_ratio_available: true, breadth: '上涨家数 3102 / 下跌 1620', sample_size: '全板块 90 个' }
  },
  '2026-11-17': {
    phase: '主线确认：龙头连续在榜，榜面开始换人', risk: '进取',
    summary: '光模块 +4.1% 创 60 日新高，需求与供给两条证据都在，结构从确认走向加速。',
    conflict: '矛盾点一：加速段延续概率最高，但追高风险同步抬升。\n矛盾点二：半导体设备有招标公告但金额未定，接力证据不够硬。',
    structure: { attack: 'CPO光模块', relay: '半导体设备', fade: 'AI应用（涨幅回落，量能不济）' },
    quality: '放量新高，量比 2.6 为近 10 日最高，成色最好的一天。',
    box: { 'CPO光模块': '箱位 90%：加速段，仓位优先给已证明业绩的环节。' },
    stocks: [{ name: '中际旭创', code: '300308', chg: 6.2, vol: 2.6, box: 90, verdict: '加速后段' }, { name: '北方华创', code: '002371', chg: 2.2, vol: 1.7, box: 60, verdict: '真强' }],
    watch: { '量能能否维持': '量比连续两日 >2 才算真加速', '良率数据': '1.6T 良率是否到 70%' },
    meaning: '主线加速期：持有 > 新开仓，追高需要等回踩。',
    raw_extra: { board_volume_ratio_available: true, breadth: '上涨家数 2640 / 下跌 2100', sample_size: '全板块 90 个' }
  },
  '2026-11-16': {
    phase: '主线确认：周末公告落地后一致预期形成', risk: '进取',
    summary: '海外 capex 上修落地，算力链整体回到涨幅榜前列，持续天数达标，结构判定进入主线。',
    conflict: '矛盾点一：证据变硬的同时位置也变高。\n矛盾点二：算力租赁只是跟随，独立证据缺失。',
    structure: { attack: 'CPO光模块', relay: '液冷服务器', fade: '固态电池（资金撤离）' },
    quality: '放量确认，量比 2.3，主线板块上涨家数同步扩张。',
    box: { 'CPO光模块': '箱位 88%：突破后第二个交易日。' },
    stocks: [{ name: '新易盛', code: '300502', chg: 4.4, vol: 2.2, box: 86, verdict: '真强' }, { name: '中际旭创', code: '300308', chg: 3.4, vol: 2.3, box: 87, verdict: '真强' }],
    watch: { '资金是否继续加仓': '主力净流入是否连续三日为正' },
    meaning: '主线确认期：可分批参与已证明业绩的环节。',
    raw_extra: { board_volume_ratio_available: true, breadth: '上涨家数 3320 / 下跌 1420', sample_size: '全板块 90 个' }
  },
  '2026-11-13': {
    phase: '主线雏形：光模块重回第一，但只有报告级证据', risk: '中性',
    summary: '板块回到涨幅第一，持续天数刚达标；证据是卖方报告而不是公告，判定给到主线确认但置信度打折。',
    conflict: '矛盾点一：结构已达标，证据等级还差一档。\n矛盾点二：液冷只有两只整机股在涨，上涨家数 26 家，广度不足。',
    structure: { attack: 'CPO光模块', relay: '算力租赁', fade: '固态电池' },
    quality: '量比 2.1 但上涨家数集中在头部，广度偏窄。',
    box: { 'CPO光模块': '箱位 84%：突破位附近。' },
    stocks: [{ name: '中际旭创', code: '300308', chg: 3.9, vol: 2.1, box: 84, verdict: '真强' }],
    watch: { '公告是否跟进': '报告级证据需要公告确认才能升档' },
    meaning: '先按主线对待，但仓位给证据升档后的部分。',
    raw_extra: { board_volume_ratio_available: true, breadth: '上涨家数 2210 / 下跌 2480', sample_size: '全板块 90 个' }
  },
  '2026-11-12': {
    phase: '混沌市：算力链回流但还没形成抱团', risk: '中性',
    summary: '存储/半导体/AI 应用交替领先，没有一个板块连续三天在 top5，结构判不出主线。',
    conflict: '矛盾点一：题材热度在回升，但没有持续性证据。\n矛盾点二：算力租赁第一次进榜（第 9 名），是新增还是脉冲未知。',
    structure: { attack: 'AI应用', relay: 'CPO光模块', fade: '煤炭开采' },
    quality: 'AI 应用量比 1.8、上涨家数 60 家，广度是这几天最好的。',
    box: { 'AI应用': '箱位 52%：中位放量，属于可能起势的位置。' },
    stocks: [{ name: '金山办公', code: '688111', chg: 3.2, vol: 1.8, box: 55, verdict: '真强' }],
    watch: { '谁先做出三天 top5': '第一个连续进榜的板块就是主线候选' },
    meaning: '混沌期不建仓，等结构定型。',
    raw_extra: { board_volume_ratio_available: true, breadth: '上涨家数 2480 / 下跌 2210', sample_size: '全板块 90 个' }
  },
  '2026-11-11': {
    phase: '混沌市：存储与半导体设备轮着第一', risk: '避险',
    summary: 'top5 内部换手不大但榜首频繁更换，缺少能带动广度的方向。',
    conflict: '矛盾点一：算力链回到榜单但涨幅收窄。\n矛盾点二：防御板块（白酒、煤炭）没有资金撤离迹象，风险偏好没打开。',
    structure: { attack: '存储芯片', relay: 'CPO光模块', fade: '光伏设备' },
    quality: '存储量比 1.7，板块上涨家数 32 家，广度一般。',
    box: { '存储芯片': '箱位 70%：反弹到压力位附近。' },
    stocks: [{ name: '兆易创新', code: '603986', chg: 2.5, vol: 1.7, box: 70, verdict: '加速后段' }],
    watch: { '榜首是否换手': '连续两日同一板块第一才算主线' },
    meaning: '降仓位、等主线。',
    raw_extra: { board_volume_ratio_available: true, breadth: '上涨家数 1980 / 下跌 2710', sample_size: '全板块 90 个' }
  },
  '2026-11-10': {
    phase: '混沌市：半导体设备单日脉冲', risk: '避险',
    summary: '半导体设备 +2.9% 拿下第一，但前一日还排在第 8，属于资金单日选择。',
    conflict: '矛盾点：榜单每天都在换人，没有持续证据，任何主线判断都会被打脸。',
    structure: { attack: '半导体设备', relay: 'AI应用', fade: '固态电池' },
    quality: '量比 1.9，上涨家数 42 家。',
    box: { '半导体设备': '箱位 58%：中位起跳。' },
    stocks: [{ name: '北方华创', code: '002371', chg: 3.1, vol: 1.9, box: 58, verdict: '真强' }],
    watch: { '次日能否守住前三': '守住才算结构，守不住就是脉冲' },
    meaning: '只做已经证明的，不做第一天冒出来的。',
    raw_extra: { board_volume_ratio_available: true, breadth: '上涨家数 1720 / 下跌 2980', sample_size: '全板块 90 个' }
  },
  '2026-11-09': {
    phase: '（该轮量能数据源缺板块量比）创新药与固态电池轮动', risk: '避险',
    summary: '轮动速度快、无主线；本轮 akshare 东财接口未返回板块量比，量能信号不完整。',
    conflict: '矛盾点：创新药有海外授权收入，固态电池只有排产传闻，两者却在同一个榜单上被同等对待。',
    structure: { attack: '创新药', relay: '', fade: '' },
    quality: '',
    box: {},
    stocks: [{ name: '恒瑞医药', code: '600276', chg: 2.7, vol: null, box: 49, verdict: '真强' }],
    watch: { '量比数据恢复': '等 akshare 板块量比接口恢复后重跑该轮' },
    meaning: '数据缺失时不出操作结论，只记录事实。',
    raw_extra: { board_volume_ratio_available: false, breadth: '上涨家数 1550 / 下跌 3160', sample_size: '全板块 90 个' }
  }
};
/* 历史批次已跑到的步骤（后端由各定时任务落库；11-20 的结构识别任务失败，见 MI_DIAG） */
const MI_DONE = {
  '2026-11-20': { regime: false, forward: false, intel: false, rotation: false, verify: false },
  '2026-11-19': { regime: true, forward: true, intel: true, rotation: true, verify: true },
  '2026-11-18': { regime: true, forward: true, intel: true, rotation: true, verify: true },
  '2026-11-17': { regime: true, forward: true, intel: true, rotation: true, verify: true },
  '2026-11-16': { regime: true, forward: true, intel: true, rotation: true, verify: true },
  '2026-11-13': { regime: true, forward: true, intel: true, rotation: true, verify: true },
  '2026-11-12': { regime: true, forward: true, intel: true, rotation: false, verify: true },
  '2026-11-11': { regime: true, forward: true, intel: true, rotation: false, verify: true },
  '2026-11-10': { regime: true, forward: true, intel: true, rotation: false, verify: true },
  '2026-11-09': { regime: false, forward: false, intel: true, rotation: false, verify: false },
  '2026-11-06': { regime: false, forward: false, intel: false, rotation: false, verify: false },
  '2026-11-05': { regime: false, forward: false, intel: false, rotation: false, verify: false },
  '2026-11-04': { regime: false, forward: false, intel: false, rotation: false, verify: false },
  '2026-11-03': { regime: false, forward: false, intel: false, rotation: false, verify: false }
};

/* ---------- 市场研判：判定引擎（后端同一套公式的浏览器镜像） ---------- */
const MI_DB_DAYS = 68;
const MI_REGIME_LABEL = { mainline: '主线行情', rotation: '轮动行情', chaos: '混沌行情', unknown: '数据缺失' };
const MI_STAGE_LABEL = { start: '启动', confirm: '确认', accelerate: '加速', diverge: '分歧', fade: '退潮', unknown: '未定档' };
const MI_BIAS_LABEL = {
  continue: '延续', switch: '切换', fade: '退潮', diverge: '分歧', uncertain: '不确定',
  mainline_confirm: '主线确认', new_mainline_switch: '新主线切换', invalid_rotation: '无效轮动'
};
const MI_TONE_LABEL = { continue: 'green', mainline_confirm: 'green', switch: 'blue', new_mainline_switch: 'blue', fade: 'red', diverge: 'gold', uncertain: 'mute', invalid_rotation: 'red' };
const MI_APPETITE = {
  进取: { tone: 'red', 含义: '资金转进攻，可增配主线强势方向' },
  中性: { tone: 'mute', 含义: '资金偏好均衡，维持中性仓位右侧确认' },
  避险: { tone: 'gold', 含义: '资金退守防御，控制仓位等待企稳' }
};
/* 结构判定这块的已知毛病：对着后端代码核过，正式落地要修，页面上照实列出来 */
const MI_REGIME_GAPS = [
  ['没有手动补跑结构的接口', 'C′ 只在 15:40 定时任务里跑，接口层只暴露了 D′ 板块前瞻。结构记录缺失时点「刷新行情结构」会直接报「行情结构预测不存在」，页面只能显示空态。要能补历史，需要新增一个手动跑 C′ 的接口。'],
  ['回填历史日期时置信度恒等于 20%', '取数先拉「全库最近 60 个交易日」再按当天切片，窗口长度跟着日期越靠后越短。回填一周前的数据时只剩 53 天，触发「不足 60 日」规则把置信度压到 20%，看上去像模型没信心，实际是可用样本被 60 条上限截掉了。'],
  ['阶段档位有够不到的分支', '「启动」要求龙头连续正好 2 天，但主线判定本身要求连续 ≥3 天，两个条件互斥；「退潮」同样要求连续 <3 天。正式环境里这两个档位基本不会出现，页面按六档渲染会一直空着。'],
  ['「加速」档天生和高换手绑在一起', '加速要同时满足连续 ≥3 天、量比扩张 >0.2、前五箱位中位数 ≥0.7。但它排在「确认」之后判断，而确认吃掉了所有榜面换手 <0.5 的日子，所以只有换手已经打到 ≥0.5 时才轮得到加速——「加速」实际含义变成了「高换手 + 放量 + 高位」，和量价扩张的本意不一样。原型 22 个交易日里只出现过 1 次，换口径后要在生产数据上复算分布。'],
  ['箱位没取到时，页面会显示成「行情不确定」', '两边都把箱位取数做成了超时降级（拿不到就当空），但降级不等于无害：板块前瞻的延续概率要同时用量比和箱位，箱位缺失时这一项直接算不出来，三个窗口的倾向全部落到「不确定」；结构判定这边，箱位缺失会让「加速」档永远不触发。看上去是行情看不清，实际是取数没成功。落地要区分「箱位缺失」和「箱位很低」，缺失时按去掉位置项的归一公式继续算，并把降级原因写进证据字段给页面显示。'],
  ['结构阶段直接显示英文枚举', '正式页面把 regime_stage 原样输出（forward_bias 已经过了中文映射），「accelerate」「diverge」这种字样业务看不懂，需要中文映射与配色。本页用固定六档映射，不临场造词。'],
  ['回填历史日期时偷看了未来', '连续居前天数读的是「该板块全库最新 10 日快照」，函数不接受截止日期参数。补跑一周前的结构时，这一项用的是那一周之后的行情，主线连续天数会被未来的行情抬高或压低，连带落库的结构记录和后验准确率都不干净。回填前要给这个取数加 as-of 日期。']
];
const MI_BOARDS = [
  ['regime', '行情结构'], ['basis', '市场判定依据'], ['conflict', '核心矛盾'], ['volume', '板块量能信号'],
  ['operative', '操作含义'], ['watch', '次日盯盘点'], ['rotation', '板块轮动归因'], ['raw', '原始返回']
];
const MI_BOARD_NOTE = {
  regime: '结构判定（3/10/20/60 日窗口）+ 板块三窗口前瞻 + 历史准确率，全部由日快照现算',
  basis: '支撑本轮「阶段定性」的关键数据与证据，缺失字段照实显示（未提供）',
  conflict: 'AI 认为这一轮最纠结的点，以及它选择怎么处理',
  volume: '放量/缩量/极端量能来自板块快照；数据源不返回板块量比时按缺失处理，不猜',
  operative: '箱位理解 + 主线板块内个股三维验证：涨幅、量比、60 日箱位合不合得上',
  watch: '明天开盘要盯的具体条件，每个都给了「出现什么就改判断」',
  rotation: 'AI 启动归因（约 5 分钟长跑）+ top10 之外的「下一个风口」快速替代 + 多窗口规律',
  raw: '给排查用：接口原始返回与判定输入，业务判断看上面的看板'
};

function miDates() {
  return MI_OLD_TOP5.map((d) => d[0]).concat(MI_DAILY.map((d) => d[0]));
}
function miIdx(date) { return miDates().indexOf(date); }
function miDay(i) {
  const o = MI_OLD_TOP5.length;
  if (i < o) {
    return {
      date: MI_OLD_TOP5[i][0],
      partial: true,
      rows: MI_OLD_TOP5[i][1].map((n, k) => ({ sector: n, rank: k + 1, chg: null, vol: null, up: null }))
    };
  }
  const day = MI_DAILY[i - o];
  /* rank_no 就是当日涨幅名次：先按涨幅排序再编号，表里手写顺序不会和数字打架 */
  return {
    date: day[0], partial: false,
    rows: day[1].slice().sort((a, b) => b[1] - a[1])
      .map((r, k) => ({ sector: r[0], rank: k + 1, chg: r[1], vol: r[2], up: r[3] }))
  };
}
function miTop(i, n) { return i < 0 || i >= miDates().length ? [] : miDay(i).rows.slice(0, n || 5).map((r) => r.sector); }
function miRowOf(i, sector) {
  if (i < 0 || i >= miDates().length) return null;
  const hit = miDay(i).rows.filter((r) => r.sector === sector)[0];
  return hit || null;
}
function miBox(sector, i) {
  const last = miDates().length - 1;
  if (MI_BOX_MISSING.date === miDates()[i] && MI_BOX_MISSING.sectors.indexOf(sector) >= 0) return null;
  const base = MI_BOX_LATEST[sector];
  if (base == null) return null;
  const slope = MI_BOX_SLOPE[sector] || 0;
  return Math.max(0.02, Math.min(0.99, base - slope * (last - i) / 20));
}
function miClamp(v) { return v == null || isNaN(v) ? null : Math.max(0, Math.min(1, v)); }
function miMean(list) {
  const vals = list.filter((v) => v != null && !isNaN(Number(v))).map(Number);
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
}
function miMedian(list) {
  const vals = list.filter((v) => v != null && !isNaN(Number(v))).map(Number).sort((a, b) => a - b);
  if (!vals.length) return null;
  const h = Math.floor(vals.length / 2);
  return vals.length % 2 ? vals[h] : (vals[h - 1] + vals[h]) / 2;
}
/* 连续进入涨幅榜前五的天数（从今天往回数，最多 10 日） */
function miStreak(sector, i) {
  let n = 0;
  for (let k = i; k >= 0 && n < 10; k--) {
    const r = miRowOf(k, sector);
    if (!r || r.rank > 5) break;
    n += 1;
  }
  return n;
}
function miHist(sector, i) {
  const out = [];
  for (let k = Math.max(0, i - 9); k <= i; k++) {
    const r = miRowOf(k, sector);
    if (r) out.push(Object.assign({ date: miDates()[k] }, r));
  }
  return out;
}
function miTop10Freq(sector, i) {
  const total = Math.min(10, i + 1);
  if (!total) return 0;
  return miHist(sector, i).filter((r) => r.rank <= 10).length / 10;
}
/* top5 换手率：今天与往前三个交易日逐对比对，1 - 重合数/5，取平均 */
function miChurn3(i) {
  const pairs = [];
  for (let k = 0; k < 3 && i - k - 1 >= 0; k++) {
    const a = miTop(i - k, 5), b = miTop(i - k - 1, 5);
    const overlap = a.filter((n) => b.indexOf(n) >= 0).length;
    pairs.push(1 - overlap / 5);
  }
  return pairs.length ? miMean(pairs) : null;
}
/* 今日前三板块在过去 20 个交易日里「至少一个还在 top5」的天数占比 */
function miPersist(i) {
  const top3 = miTop(i, 3);
  if (!top3.length) return null;
  const from = Math.max(0, i - 19);
  let hits = 0;
  for (let k = from; k <= i; k++) {
    const t5 = miTop(k, 5);
    if (t5.some((n) => top3.indexOf(n) >= 0)) hits += 1;
  }
  /* 后端分母是 min(20, 截断窗口天数)，不是实际取到的快照条数 */
  return hits / Math.min(20, miWindowDays(i));
}
function miWindowDays(i) {
  const back = miDates().length - 1 - i;
  return Math.min(MI_WINDOW_LIMIT, MI_DB_DAYS - back);
}
function miMetrics(i) {
  const top5 = miDay(i).rows.slice(0, 5);
  const streaks = top5.map((r) => ({ sector: r.sector, n: miStreak(r.sector, i) }));
  const leader = streaks.slice().sort((a, b) => b.n - a.n)[0] || null;
  const old = miDay(Math.max(0, i - 2));
  const oldTop5 = old.rows.slice(0, 5);
  const recentUp = miMean(top5.map((r) => r.up));
  const oldUp = miMean(oldTop5.map((r) => r.up));
  const recentVol = miMean(top5.map((r) => r.vol));
  const oldVol = miMean(oldTop5.map((r) => r.vol));
  const boxes = top5.map((r) => miBox(r.sector, i));
  return {
    leader_streak_max_10d: leader ? leader.n : 0,
    leader_streak_sector: leader ? leader.sector : null,
    top5_churn_3d: miChurn3(i),
    top3_persistence_20d: miPersist(i),
    breadth_expansion_10d: (recentUp != null && oldUp != null) ? miClamp((recentUp - oldUp) / Math.max(Math.abs(oldUp || 1), 1)) : null,
    volume_confirm_3d: (recentVol != null && oldVol != null) ? miClamp(recentVol - oldVol) : null,
    box_position_median_60d: miMedian(boxes) == null ? null : miMedian(boxes),
    box_missing_count: boxes.filter((b) => b == null).length,
    window_days: miWindowDays(i),
    data_insufficient: miWindowDays(i) < MI_WINDOW_LIMIT
  };
}
/* C' 行情结构判定（sector_regime.judge_regime） */
function miRegime(i) {
  const e = miMetrics(i);
  const streak = e.leader_streak_max_10d;
  const persist = e.top3_persistence_20d || 0;
  const churn = e.top5_churn_3d || 0;
  const box = e.box_position_median_60d;
  const vol = e.volume_confirm_3d || 0;
  let regime, stage;
  if (streak >= 3 && persist >= 0.6) regime = 'mainline';
  else if (churn >= 0.6 && streak < 3) regime = 'rotation';
  else regime = 'chaos';
  if (regime !== 'mainline') stage = 'unknown';
  else if (streak === 2) stage = 'start';
  else if (streak >= 3 && persist >= 0.6 && churn < 0.5) stage = 'confirm';
  else if (streak >= 3 && vol > 0.2 && (box || 0) >= 0.7) stage = 'accelerate';
  else if (streak >= 3 && churn >= 0.5) stage = 'diverge';
  else if (streak < 3 && (box || 0) >= 0.7) stage = 'fade';
  else stage = 'unknown';
  let t1, t3, t5;
  if (regime === 'mainline' && (stage === 'start' || stage === 'confirm')) { t1 = 'continue'; t3 = 'continue'; t5 = 'mainline_confirm'; }
  else if (regime === 'mainline' && (stage === 'accelerate' || stage === 'diverge')) {
    t1 = stage === 'accelerate' ? 'fade' : 'switch'; t3 = 'diverge'; t5 = 'new_mainline_switch';
  } else if (regime === 'rotation') { t1 = 'switch'; t3 = 'switch'; t5 = 'invalid_rotation'; }
  else { t1 = 'uncertain'; t3 = 'uncertain'; t5 = 'uncertain'; }
  let confidence = regime === 'mainline' ? Math.min(1, 0.7 + 0.1 * Math.min(streak, 3))
    : regime === 'rotation' ? Math.min(0.8, 0.5 + 0.1 * Math.min(churn * 10, 3)) : 0.4;
  if (e.data_insufficient) confidence = 0.2;
  return {
    trade_date: miDates()[i], current_regime: regime, regime_stage: stage, regime_confidence: confidence,
    forward_bias_t1: t1, forward_bias_t3: t3, forward_bias_t5: t5, evidence: e,
    notes: 'window_days=' + e.window_days
  };
}
/* 归因上下文（sector_forward_view._causal_context）：当日有归因就用它的置信度，没有就找历史同日并标「当日归因缺失」 */
function miCausal(i, sector) {
  const date = miDates()[i];
  const cur = (MI_LAUNCH[date] || []).filter((l) => l.sector === sector)[0];
  if (cur) {
    const hard = (cur.causal || []).some((c) => c.level === 'L1' || c.level === 'L2');
    return {
      causal_missing: false, source_trade_date: date, confidence: cur.confidence, reason_tags: cur.tags,
      falsification: { triggered: !!(cur.falsify && cur.falsify.triggered) },
      has_hard_evidence: hard, has_transmission: !!cur.transmission, has_capital_behavior: !!cur.capital,
      record: cur
    };
  }
  const dates = miDates();
  for (let k = i - 1; k >= 0; k--) {
    const old = (MI_LAUNCH[dates[k]] || []).filter((l) => l.sector === sector)[0];
    if (old) {
      return {
        causal_missing: true, background_available: true, source_trade_date: dates[k], confidence: null,
        reason_tags: '', falsification: {}, has_hard_evidence: false, has_transmission: false,
        has_capital_behavior: false, record: old
      };
    }
  }
  return {
    causal_missing: true, background_available: false, source_trade_date: null, confidence: null,
    reason_tags: '', falsification: {}, has_hard_evidence: false, has_transmission: false,
    has_capital_behavior: false, record: null
  };
}
/* D' 板块前瞻（sector_forward_view._score：延续/退潮/追高三个概率 + 倾向） */
function miScore(i, row, regime) {
  const hist = miHist(row.sector, i);
  const previous = hist.length >= 2 ? hist[hist.length - 2] : null;
  const causal = miCausal(i, row.sector);
  const top10Freq = miHist(row.sector, i).filter((r) => r.rank <= 10).length / 10;
  const streak = miStreak(row.sector, i);
  const volumeTerm = row.vol == null ? null : miClamp(1 - Math.abs(row.vol - 1));
  const box = miBox(row.sector, i);
  const highBox = box != null && box >= 0.7 ? 1 : 0;
  const historicalUp = miMean(hist.map((r) => r.up)) || 1;
  const breadth = row.up == null ? null : miClamp((row.up / historicalUp) - 1);
  let continuation = (volumeTerm != null && box != null)
    ? miClamp(0.35 * top10Freq + 0.20 * volumeTerm + 0.20 * miClamp(streak / 5) + 0.15 * (breadth || 0) + 0.10 * (1 - highBox))
    : null;
  const streakGe5 = streak >= 5 ? 1 : 0;
  const volumeFade = (row.vol != null && previous && previous.vol != null && previous.vol !== 0 && row.vol / previous.vol < 0.8) ? 1 : 0;
  const rankDrop = miClamp(((row.rank || 10) - ((previous && previous.rank) || row.rank || 10)) / 10);
  let exhaustion = miClamp(0.40 * highBox + 0.30 * streakGe5 + 0.20 * volumeFade + 0.10 * rankDrop);
  const surge = miClamp((row.chg || 0) / 10);
  let chase = miClamp(0.5 * surge + 0.3 * (1 - top10Freq) + 0.2 * highBox);
  let causalAdjustment = null;
  if (continuation != null && !causal.causal_missing && causal.confidence != null) {
    if (causal.confidence >= 0.75) { continuation = miClamp(continuation + 0.05); causalAdjustment = 0.05; }
    else if (causal.confidence < 0.45) { continuation = miClamp(continuation - 0.05); chase = miClamp(chase + 0.05); causalAdjustment = -0.05; }
    else causalAdjustment = 0;
  }
  const falsified = !!(causal.falsification && causal.falsification.triggered);
  if (falsified) {
    if (continuation != null) continuation = miClamp(continuation - 0.05);
    exhaustion = miClamp((exhaustion || 0) + 0.05);
    chase = miClamp(chase + 0.05);
  }
  const mainline = regime.current_regime === 'mainline';
  const fading = ['diverge', 'fade'].indexOf(regime.regime_stage) >= 0 &&
    regime.evidence.leader_streak_sector !== row.sector;
  const top10Two = hist.length >= 2 && hist.slice(-2).every((r) => r.rank <= 10);
  const expanding = row.vol != null && previous && previous.vol != null && row.vol > previous.vol;
  const switchCand = box != null && box < 0.7 && top10Two && !!expanding && fading;
  const base = continuation != null && continuation >= 0.6 && (exhaustion || 0) < 0.6 ? 'continue'
    : switchCand ? 'switch' : (exhaustion || 0) >= 0.6 ? 'fade' : 'uncertain';
  const emotionOnly = String(causal.reason_tags || '').split(',').indexOf('emotion_only') >= 0;
  let sectorTag = 'none';
  if (switchCand && continuation != null && continuation >= 0.5 && streak >= 2) sectorTag = 'mainline_seed';
  else if (exhaustion >= 0.6) sectorTag = 'fade_warn';
  else if (regime.regime_stage === 'accelerate' && chase >= 0.5) sectorTag = 'accelerate_warn';
  else if (exhaustion < 0.4 && continuation != null && continuation >= 0.5 && box != null && box < 0.6) sectorTag = 'low_buy';
  else if (chase >= 0.6 && top10Freq < 0.3 && streak < 2) sectorTag = 'one_day_fly';
  /* 情绪票不给接力资格：种子/低位可买一律降成一日游（后端同一条规则） */
  if (emotionOnly && (sectorTag === 'mainline_seed' || sectorTag === 'low_buy')) sectorTag = 'one_day_fly';
  const biasOf = (h) => {
    let b = base;
    if (h === 't3') b = (exhaustion || 0) >= 0.6 ? 'diverge' : b;
    else if (h === 't5') {
      b = switchCand ? 'new_mainline_switch' : (exhaustion || 0) >= 0.6 ? 'fade'
        : base === 'continue' ? 'mainline_confirm' : regime.current_regime === 'rotation' ? 'invalid_rotation' : 'uncertain';
    }
    if (falsified) b = { continue: 'uncertain', mainline_confirm: 'uncertain', new_mainline_switch: 'switch' }[b] || b;
    if (emotionOnly && ['t3', 't5'].indexOf(h) >= 0 && (b === 'continue' || b === 'mainline_confirm')) b = 'uncertain';
    return b;
  };
  return {
    sector: row.sector, rank_no: row.rank, box, streak, top10_freq: top10Freq,
    continuation_prob: continuation, exhaustion_risk: exhaustion, chase_risk: chase,
    sector_tag: sectorTag,
    switch_candidate: switchCand, forward_bias_t1: biasOf('t1'), forward_bias_t3: biasOf('t3'), forward_bias_t5: biasOf('t5'),
    causal, causal_adjustment: causalAdjustment, falsified, emotion_only: emotionOnly,
    evidence: {
      box_position_60d: box, streak, top10_freq_10d: top10Freq, volume_ratio: row.vol,
      technical_continuation_prob: box != null && volumeTerm != null
        ? miClamp(0.35 * top10Freq + 0.20 * volumeTerm + 0.20 * miClamp(streak / 5) + 0.15 * (breadth || 0) + 0.10 * (1 - highBox)) : null,
      causal_confidence: causal.confidence, causal_missing: causal.causal_missing,
      causal_source_trade_date: causal.source_trade_date, causal_reason_tags: causal.reason_tags,
      falsification_triggered: falsified, data_insufficient: hist.length < 10
    }
  };
}
function miForecasts(i, regime) {
  /* D' 依赖 C' 的结构结论：结构没跑出来就不出前瞻（后端同样直接报错） */
  const rg = regime || (miRun(i).regime ? miRegime(i) : null);
  if (!rg) return [];
  return miDay(i).rows.slice(0, 10).map((r) => miScore(i, r, rg));
}
/* E'-1 后验：用预测日之后的真实快照回看命中（sector_forecast_verify.evaluate_forecast） */
function miVerifyOne(i, horizon, regime, forecasts) {
  const need = { t1: 1, t3: 3, t5: 5 }[horizon];
  const dates = miDates();
  const win = dates.slice(i + 1, i + 1 + need);
  const norm = (b) => b === 'mainline_confirm' ? 'continue' : b === 'new_mainline_switch' ? 'switch' : b === 'invalid_rotation' ? 'diverge' : (b || 'uncertain');
  const mainline = regime.evidence.leader_streak_sector || ((forecasts.filter((f) => f.rank_no === 1)[0] || {}).sector || null);
  const sw = (forecasts.filter((f) => f.switch_candidate)[0] ||
    forecasts.filter((f) => f.sector !== mainline && norm(f['forward_bias_' + horizon]) === 'switch')[0] ||
    forecasts.filter((f) => f.sector !== mainline)[0] || {}).sector || null;
  const bias = regime['forward_bias_' + horizon];
  const prediction = norm(bias);
  const causalReview = (hit) => {
    const target = forecasts.filter((f) => f.sector === mainline)[0] || forecasts[0];
    const conf = target ? target.evidence.causal_confidence : null;
    const missing = !target || target.evidence.causal_missing || conf == null;
    const band = missing ? 'missing' : conf >= 0.75 ? 'high' : conf >= 0.45 ? 'medium' : 'low';
    const gaps = [];
    if (!missing) {
      if (!target.causal.has_hard_evidence) gaps.push('缺 L1/L2 硬证据');
      if (!target.causal.has_transmission) gaps.push('缺产业传导链条');
      if (!target.causal.has_capital_behavior) gaps.push('缺资金行为验证');
    } else gaps.push('当日归因缺失');
    return {
      sector: target ? target.sector : null, confidence: conf, band, gaps,
      source: target ? target.evidence.causal_source_trade_date : null,
      status: missing ? 'causal_missing' : hit == null ? 'awaiting_market_verification' : hit ? 'market_validated' : 'market_not_validated'
    };
  };
  if (win.length < need) {
    return {
      forecast_date: dates[i], verify_horizon: horizon, verify_date: null, regime_forecast: regime.current_regime,
      prediction, regime_hit: null, top5_continue_rate: null, mainline_hit: null,
      miss_reason: 'data_insufficient', missing_days: need - win.length,
      detail: { required_days: need, actual_days: win.length, causal_review: causalReview(null) }
    };
  }
  const rowsByDay = win.map((d) => miDay(dates.indexOf(d)));
  const top5ByDay = rowsByDay.map((r) => r.rows.slice(0, 5).map((x) => x.sector));
  const top10ByDay = rowsByDay.map((r) => r.rows.slice(0, 10).map((x) => x.sector));
  const sumChange = (name) => {
    let s = 0, ok = true;
    rowsByDay.forEach((r) => {
      const row = r.rows.filter((x) => x.sector === name)[0];
      if (!row || row.chg == null) ok = false; else s += row.chg;
    });
    return ok ? s : null;
  };
  const first = rowsByDay[0], last = rowsByDay[rowsByDay.length - 1];
  const firstMain = first.rows.filter((r) => r.sector === mainline)[0] || null;
  const finalMain = last.rows.filter((r) => r.sector === mainline)[0] || null;
  const finalSw = last.rows.filter((r) => r.sector === sw)[0] || null;
  const mainTop5Days = top5ByDay.filter((t) => t.indexOf(mainline) >= 0).length;
  const initialTop5 = forecasts.filter((f) => f.rank_no <= 5).map((f) => f.sector);
  const newTop5First = top5ByDay[0].some((n) => initialTop5.indexOf(n) < 0);
  const mainSum = sumChange(mainline), swSum = sumChange(sw);
  const leaders = rowsByDay.map((r) => r.rows[0] && r.rows[0].sector).filter(Boolean);
  const inter = top5ByDay.reduce((a, t) => a.filter((n) => t.indexOf(n) >= 0), top5ByDay[0] || []);
  let posterior = 'chaos';
  if (rowsByDay.length < 2) posterior = null;
  else if (inter.length >= 3) posterior = 'mainline';
  else if (new Set(leaders).size >= Math.min(3, leaders.length)) posterior = 'rotation';
  let hit = null, reason = 'rule_miss';
  if (prediction === 'uncertain') {
    reason = 'uncertain';
  } else if (prediction === 'continue') {
    hit = horizon === 't1' ? !!(firstMain && firstMain.rank <= 5 && firstMain.chg > 0)
      : horizon === 't3' ? mainTop5Days === 3 : (mainSum != null && mainSum > 0);
  } else if (prediction === 'switch') {
    hit = horizon === 't1' ? newTop5First
      : horizon === 't3' ? !!(finalSw && finalSw.rank <= 5 && (!finalMain || finalMain.rank > 5))
        : (swSum != null && swSum > 0);
  } else if (prediction === 'fade') {
    hit = horizon === 't1' ? (!firstMain || firstMain.rank > 10)
      : horizon === 't3' ? top10ByDay.some((t) => t.indexOf(mainline) < 0)
        : (mainSum != null && mainSum < 0);
  } else if (prediction === 'diverge') {
    hit = horizon === 't1' ? regime.regime_stage === 'diverge'
      : horizon === 't3' ? new Set(leaders).size >= 2 : !!(finalSw && finalSw.rank <= 5);
  }
  if (hit && reason === 'rule_miss') reason = '';
  return {
    forecast_date: dates[i], verify_horizon: horizon, verify_date: win[win.length - 1],
    regime_forecast: regime.current_regime, prediction,
    regime_hit: posterior == null ? null : regime.current_regime === posterior,
    top5_continue_rate: mainline ? mainTop5Days / need : null,
    mainline_hit: prediction === 'uncertain' ? null : hit,
    miss_reason: prediction === 'uncertain' ? 'uncertain' : reason,
    uncertain: prediction === 'uncertain',
    detail: {
      posterior_regime: posterior, mainline_sector: mainline, switch_sector: sw,
      mainline_change_sum: mainSum, switch_change_sum: swSum, window: win,
      causal_review: causalReview(prediction === 'uncertain' ? null : hit)
    }
  };
}
function miVerify(i, regime, forecasts) {
  return ['t1', 't3', 't5'].map((h) => miVerifyOne(i, h, regime, forecasts));
}
function miAccuracy(i) {
  const dates = miDates();
  const out = [];
  [{ d: 7, label: '近 7 日' }, { d: 30, label: '近 30 日' }, { d: 90, label: '近 90 日' }].forEach((w) => {
    const samples = [];
    for (let k = Math.max(0, i - w.d + 1); k <= i; k++) {
      if (!miRun(k).regime) continue;
      const rg = miRegime(k), fc = miForecasts(k, rg);
      miVerify(k, rg, fc).forEach((v) => samples.push({ regime: rg.current_regime, v, f: fc }));
    }
    const done = samples.filter((s) => s.v.miss_reason !== 'data_insufficient');
    const groups = ['mainline', 'rotation', 'chaos'].map((rg) => {
      const g = done.filter((s) => s.regime === rg);
      return {
        regime: rg, sample_count: g.length,
        regime_hit_rate: g.length ? g.filter((s) => s.v.regime_hit).length / g.length : null,
        top5_continue_rate: miMean(g.map((s) => s.v.top5_continue_rate)),
        mainline_hit_rate: g.length ? (function () {
          const h = g.filter((s) => s.v.mainline_hit != null);
          return h.length ? h.filter((s) => s.v.mainline_hit).length / h.length : null;
        })() : null
      };
    });
    const bands = [['high', '高'], ['medium', '中'], ['low', '低'], ['missing', '缺失']].map((b) => {
      const g = done.filter((s) => s.v.detail.causal_review.band === b[0]);
      return {
        band: b[0], label: b[1], sample_count: g.length,
        regime_hit_rate: g.length ? g.filter((s) => s.v.regime_hit).length / g.length : null,
        top5_continue_rate: miMean(g.map((s) => s.v.top5_continue_rate)),
        mainline_hit_rate: (function () {
          const h = g.filter((s) => s.v.mainline_hit != null);
          return h.length ? h.filter((s) => s.v.mainline_hit).length / h.length : null;
        })()
      };
    });
    out.push({
      window_days: w.d, label: w.label, sample_count: done.length, pending: samples.length - done.length,
      start_date: dates[Math.max(0, i - w.d + 1)], end_date: dates[i], groups, causal_groups: bands
    });
  });
  return { windows: out };
}
function miVolumeSignal(i, base) {
  const rows = miDay(i).rows;
  const date = miDates()[i];
  const intel = base || MI_INTEL[date];
  const avail = !(intel && intel.raw_extra && intel.raw_extra.board_volume_ratio_available === false);
  const strong = rows.filter((r) => avail && r.vol >= 1.8).map((r) => r.sector);
  const weak = rows.filter((r) => avail && r.vol <= 0.8).map((r) => r.sector);
  const peak = rows.filter((r) => avail && r.vol >= 2.3).map((r) => r.sector + '（量比 ' + r.vol.toFixed(1) + '）');
  return {
    available: avail,
    放量板块: strong.length ? strong.join('、') : '（无）',
    缩量板块: weak.length ? weak.join('、') : '（无）',
    极端量能: peak.length ? peak.join('、') : '',
    分布: rows.slice(0, 5).map((r) => r.sector + ' ' + (r.vol == null ? '—' : r.vol.toFixed(1))).join('，'),
    量能成色: intel ? intel.quality : '',
    主线结构: intel ? intel.structure : null
  };
}
function miOperativeMeaning(i, base) {
  const intel = base || MI_INTEL[miDates()[i]];
  if (!intel) return null;
  return {
    操作含义: intel.meaning,
    箱位理解: intel.box,
    个股验证: intel.stocks
  };
}
function miBuildIntel(i) {
  const date = miDates()[i];
  if (MI_INTEL[date]) return MI_INTEL[date];
  const rg = miRegime(i), e = rg.evidence;
  const top = miTop(i, 3);
  const risk = rg.current_regime === 'mainline' ? (rg.regime_stage === 'confirm' ? '进取' : '中性') : rg.current_regime === 'rotation' ? '中性' : '避险';
  return {
    phase: MI_REGIME_LABEL[rg.current_regime] + ' · 阶段' + MI_STAGE_LABEL[rg.regime_stage] + '：' + (top[0] || '—') + '领跑',
    risk,
    summary: '结构判定为' + MI_REGIME_LABEL[rg.current_regime] + '，龙头持续 ' + e.leader_streak_max_10d +
      ' 个交易日排在涨幅前五（' + (e.leader_streak_sector || '—') + '），近三日 top5 换手 ' + (e.top5_churn_3d == null ? '—' : e.top5_churn_3d.toFixed(2)) +
      '。这段结论文案由模板按同一批数字拼出，正式系统由 16:20 的大模型研判产出。',
    conflict: '这一轮的矛盾点：' + (rg.current_regime === 'mainline'
      ? '结构已经成型（前三板块 20 日留存 ' + Math.round((e.top3_persistence_20d || 0) * 100) + '%），但 60 日箱位中位数已到 ' +
        Math.round((e.box_position_median_60d || 0) * 100) + '%，位置与证据同时到位意味着容错变小。'
      : '榜单换手快（近三日 top5 换手 ' + (e.top5_churn_3d == null ? '—' : e.top5_churn_3d.toFixed(2)) + '），' +
        '没有一个板块做出足够长的持续性，任何主线判断都可能第二天被打脸。'),
    structure: { attack: top[0] || '（无）', relay: top[1] || '（无）', fade: miTop(i, 10).slice(-1)[0] || '（无）' },
    quality: '', box: {}, stocks: [], watch: { '次日榜首': '若换人，则本轮结构判定要重新跑' },
    meaning: '模板生成的占位操作含义，正式系统由 AI 结合当日消息面撰写。',
    raw_extra: { board_volume_ratio_available: true, generated_by: 'prototype_template', breadth: '（原型未提供）', sample_size: '全板块 90 个' }
  };
}
function miIntel(i) {
  const date = miDates()[i];
  const base = MI_INTEL[date] || (miRun(i).intel ? miBuildIntel(i) : null);
  if (!base) return null;
  const vs = miVolumeSignal(i, base);
  return {
    trade_date: date, phase: base.phase, risk_appetite: base.risk, core_conflict: base.conflict,
    summary: base.summary, volume_signal: vs, operative_meaning: miOperativeMeaning(i, base),
    next_day_watch: base.watch, raw: Object.assign({}, base.raw_extra, { generated_by: MI_INTEL[date] ? 'llm' : 'prototype_template' })
  };
}
function miRun(i) {
  const date = miDates()[i];
  const seed = MI_DONE[date] || { regime: false, forward: false, intel: false, rotation: false, verify: false };
  if (!state.miRuns) state.miRuns = {};
  if (!state.miRuns[date]) state.miRuns[date] = Object.assign({}, seed);
  return state.miRuns[date];
}
function miLog(i, step, text) {
  const date = miDates()[i];
  if (!state.miLog) state.miLog = [];
  state.miLog.unshift({ date, step, text, at: new Date().toTimeString().slice(0, 8) });
  if (state.miLog.length > 12) state.miLog.pop();
}
function miBand(conf, missing) {
  if (missing || conf == null || isNaN(Number(conf))) return { label: '原因缺失', tone: 'mute' };
  const v = Number(conf);
  if (v >= 0.75) return { label: '高硬度', tone: 'green' };
  if (v >= 0.45) return { label: '中等', tone: 'gold' };
  return { label: '低硬度', tone: 'red' };
}
function miPct(v, d) {
  if (v == null || isNaN(Number(v))) return '—';
  return (Number(v) * 100).toFixed(d == null ? 0 : d) + '%';
}
function miDate() { return state.miDate && miIdx(state.miDate) >= 0 ? state.miDate : miDates()[miDates().length - 1]; }
function miI() { return miIdx(miDate()); }

/* ================= 市场研判（#/market-intel）页面渲染 ================= */
/* ---------- 市场研判：页面渲染 ---------- */
function miProb(v, kind) {
  if (v == null || isNaN(Number(v))) return '<span class="dim" title="判定输入缺失，不用猜的数补上">—</span>';
  const n = Math.round(Number(v) * 100);
  const cls = kind === 'risk' ? (n >= 70 ? 'low' : n >= 50 ? 'mid' : 'high') : n >= 60 ? 'high' : n >= 40 ? 'mid' : 'low';
  return '<div class="conf mi-conf"><div class="conf-bar"><div class="conf-fill ' + cls + '" style="width:' + n + '%"></div></div>' +
    '<span class="mono mi-conf-n">' + n + '%</span></div>';
}
function miBias(b) {
  return tag(MI_BIAS_LABEL[b] || b || '—', MI_TONE_LABEL[b] === 'mute' ? 'mute' : MI_TONE_LABEL[b] || 'mute');
}
function miRisk(v) {
  if (v == null) return '<span class="dim">—</span>';
  const n = Math.round(v * 100);
  return '<span class="mono ' + (n >= 70 ? 'bad-t' : n >= 50 ? 'warn-t' : 'dim') + '">' + n + '%</span>';
}
function miPctCell(v, d) {
  if (v == null || isNaN(Number(v))) return '<span class="dim">—</span>';
  const n = Number(v);
  return '<span class="mono ' + (n >= 0 ? 'wo-up' : 'wo-down') + '">' + (n > 0 ? '+' : '') + n.toFixed(d == null ? 1 : d) + '%</span>';
}
function miVerdict(v) {
  const map = { 真强: 'green', 加速后段: 'gold', 放量滞涨: 'gold', 假强: 'red' };
  return tag(v, map[v] || 'mute');
}
function miLevel(l) {
  return tag(l === 'L1' ? 'L1 硬证据' : l === 'L2' ? 'L2 半硬' : 'L3 盘面/传闻', l === 'L1' ? 'green' : l === 'L2' ? 'blue' : 'mute');
}
function miCauseLabel(c) {
  return { lead: '领先于涨', post_move_explanation: '涨后才找的解释', unusable_rumor: '不可用传闻' }[c] || c || '—';
}
function miStageWhy(rg) {
  const e = rg.evidence;
  const f = (v, d) => (v == null ? '—' : Number(v).toFixed(d == null ? 2 : d));
  if (rg.current_regime !== 'mainline') {
    return '龙头只排到前五连续 ' + e.leader_streak_max_10d + ' 天（要 3 天才算主线），' +
      '近三日榜面换手 ' + f(e.top5_churn_3d) + '（≥0.6 才算轮动）→ 判成' + MI_REGIME_LABEL[rg.current_regime] + '。';
  }
  return '龙头（' + esc(e.leader_streak_sector || '—') + '）连续 ' + e.leader_streak_max_10d + ' 天在涨幅前五，' +
    '前三板块 20 日留存 ' + f(e.top3_persistence_20d) + '（门槛 0.60），近三日榜面换手 ' + f(e.top5_churn_3d) +
    '，量比确认 ' + f(e.volume_confirm_3d) + '，前五箱位中位数 ' + f(e.box_position_median_60d) + ' → 阶段判成「' +
    MI_STAGE_LABEL[rg.regime_stage] + '」。';
}
function miRunBtns(i, run) {
  const steps = [
    ['mi-run-regime', '跑行情结构', run.regime, '先定结构，再算板块前瞻'],
    ['mi-run-rotation', '生成轮动归因', run.rotation, 'AI 启动归因，约 5 分钟'],
    ['mi-run-intel', '立即研判', run.intel, '16:20 那段文字结论'],
    ['mi-run-verify', '回填验证', run.verify, '用真实行情回看，算历史准确率']
  ];
  return steps.map((s) => '<button class="btn sm" data-action="' + s[0] + '"' + (s[2] ? ' disabled' : '') + '>' +
    (s[2] ? icon('check', 'sm') : icon('workflow', 'sm')) + s[1] + '</button>' +
    '<span class="hint mi-step-state ' + (s[2] ? 'done' : '') + '">' + s[3] + '</span>').join('');
}
function miLogStrip() {
  if (!state.miLog || !state.miLog.length) return '';
  return '<div class="pp-facts mi-log"><div class="pp-fact mi-log-head"><span class="pp-fact-k">本页操作</span>' +
    '<span class="pp-fact-v">只改页面状态，没有调用后端</span></div>' +
    state.miLog.map((l) => '<span class="pp-run"><b class="mono">' + esc(l.at) + '</b> ' + esc(l.date) + ' ' + esc(l.text) + '</span>').join('') +
    '<div class="pp-runlog"><button class="btn link xs" data-action="mi-clear-log">清空</button></div></div>';
}
function miConclusion(i, rg, intel) {
  const lines = [];
  if (!rg) {
    lines.push({ tone: 'warn', text: esc(miDate()) + ' 只有板块涨幅快照，还没有结构判定：这一天的结论要等你点「跑行情结构」或等定时任务补上。' });
  } else {
    const e = rg.evidence;
    lines.push({
      tone: rg.current_regime === 'mainline' ? 'ok' : rg.current_regime === 'rotation' ? 'info' : 'warn',
      text: '<b>' + MI_REGIME_LABEL[rg.current_regime] + ' · 阶段「' + MI_STAGE_LABEL[rg.regime_stage] + '」</b>　' +
        '龙头 ' + esc(e.leader_streak_sector || '—') + '（连续 ' + e.leader_streak_max_10d + ' 天进前五）；' +
        '次日倾向 ' + MI_BIAS_LABEL[rg.forward_bias_t1] + '，三日 ' + MI_BIAS_LABEL[rg.forward_bias_t3] +
        '，五日 ' + MI_BIAS_LABEL[rg.forward_bias_t5] + '。置信度 ' + Math.round(rg.regime_confidence * 100) + '%。' +
        (e.data_insufficient ? ' <span class="bad-t">输入不足 60 个交易日，置信度已压到 20%。</span>' : '')
    });
  }
  if (intel) {
    lines.push({
      tone: 'info',
      text: 'AI 研判：' + esc(intel.phase) + '　风险偏好 <b>' + esc(intel.risk_appetite) + '</b>（' +
        esc((MI_APPETITE[intel.risk_appetite] || {}).含义 || '') + '）。'
    });
  } else {
    lines.push({ tone: 'warn', text: 'AI 研判文字还没生成（16:20 的定时任务），下面「市场判定依据 / 核心矛盾 / 操作含义 / 次日盯盘点」会保持空态，不用猜的补。' });
  }
  if (!miRun(i).verify) {
    lines.push({ tone: 'warn', text: '这一天的后验还没回填：结构判完之后没打「回填验证」，历史准确率里不会计入这一轮。' });
  }
  const job = MI_DIAG.jobs.sector_regime;
  if (job.last_status === 'failed' && miDates()[i] >= job.last_run_at.slice(0, 10)) {
    lines.push({ tone: 'err', text: '行情结构定时任务上次失败（' + esc(job.last_run_at) + '）：' + esc(job.last_error) + '。' +
      '箱位取数超时按规则只影响标注，不该中断结构判定——正式代码里这一步会把整个 C′ 一起带停，属于要修的落地缺口。' });
  }
  lines.push({
    tone: 'proto', text: '静态原型说明：本页所有百分比都是页面内的判定引擎按后端同一套公式现算出来的（输入是上面那张全板块日快照表），' +
      '点「跑行情结构 / 回填验证 / 立即研判」只推进页面状态，不会调用后端、不会改数据库、不会下单。'
  });
  return '<div class="pp-banner">' + lines.map((l) =>
    '<div class="pp-banner-line ' + l.tone + '">' + (l.tone === 'proto' ? icon('info', 'sm') : icon('alert', 'sm')) +
    '<span>' + l.text + '</span></div>').join('') + '</div>';
}
function miReadiness(i) {
  const facts = [
    ['全板块日快照', MI_DIAG.tables.sector_daily.latest_date + ' · ' + MI_DIAG.tables.sector_daily.row_count + ' 个板块'],
    ['行情结构判定', MI_DIAG.tables.sector_regime_forecast.latest_date + ' · 任务 ' + (MI_DIAG.jobs.sector_regime.last_status === 'failed' ? '上次失败' : '正常')],
    ['板块三窗口前瞻', MI_DIAG.tables.sector_forward_forecast.latest_date + ' · ' + MI_DIAG.tables.sector_forward_forecast.row_count + ' 条'],
    ['预测后验', MI_DIAG.tables.sector_forecast_verify.latest_date + ' · 回填到 ' + MI_DIAG.jobs.sector_forecast_verify.last_run_at.slice(0, 10)],
    ['下一个风口', MI_DIAG.tables.sector_next_hot.latest_date + ' · ' + MI_DIAG.tables.sector_next_hot.row_count + ' 个候选'],
    ['AI 市场研判', miRun(i).intel ? miDates()[i] + ' · 已生成' : '本日期未生成', ]
  ];
  const chain = ['15:35 全板块快照', '15:40 行情结构', '15:45 板块前瞻', '15:50 下一个风口', '16:05 后验回填', '16:20 AI 研判'];
  return '<div class="pp-facts">' + facts.map((f) =>
    '<div class="pp-fact"><span class="pp-fact-k">' + esc(f[0]) + '</span><span class="pp-fact-v">' + esc(f[1]) + '</span></div>').join('') +
    '<div class="pp-runlog"><span class="pp-run mi-chain">' + chain.map((c, k) =>
      (k ? '<span class="mi-chain-arrow">→</span>' : '') + '<span class="mi-chain-step">' + esc(c) + '</span>').join('') + '</span></div></div>';
}

function renderMarketIntel() {
  const i = miI();
  const date = miDates()[i];
  const run = miRun(i);
  const rg = run.regime ? miRegime(i) : null;
  const intel = miIntel(i);
  const dates = miDates();
  const board = MI_BOARDS.some((b) => b[0] === state.miBoard) ? state.miBoard : 'regime';
  state.miBoard = board;
  const opts = dates.slice().reverse().map((d) => {
    const r = miRun(miIdx(d));
    return '<option value="' + d + '" ' + (d === date ? 'selected' : '') + '>' + d +
      (r.regime ? '' : '（无结构判定）') + (r.intel ? '' : '（无AI研判）') + '</option>';
  }).join('');
  const chips = dates.slice().reverse().slice(0, 10).map((d) => {
    const r = miRun(miIdx(d));
    return '<button class="cp-chip ' + (d === date ? 'active' : '') + '" data-action="mi-date" data-date="' + d + '">' + d.slice(5) +
      '<span class="mi-dot ' + (r.regime ? (r.intel ? 'full' : 'part') : 'none') + '"></span></button>';
  }).join('');
  const boards = '<div class="rv-boards"><div class="cp-chips">' + MI_BOARDS.map((b) =>
    '<button class="cp-chip ' + (board === b[0] ? 'active' : '') + '" data-action="mi-board" data-b="' + b[0] + '">' + b[1] + '</button>').join('') +
    '</div><span class="hint">' + esc(MI_BOARD_NOTE[board] || '') + '</span></div>';
  const body = board === 'regime' ? miBoardRegime(i, rg, run)
    : board === 'basis' ? miBoardBasis(i, run)
    : board === 'conflict' ? miBoardConflict(i, rg, intel)
    : board === 'volume' ? miBoardVolume(i, intel)
    : board === 'operative' ? miBoardOperative(i, intel)
    : board === 'watch' ? miBoardWatch(i, intel)
    : board === 'rotation' ? miBoardRotation(i, rg, run)
    : miBoardRaw(i, rg, intel, run);
  return '<div class="page-head"><div>' +
      '<div class="page-title">市场研判</div>' +
      '<div class="page-sub">收盘后系统怎么判断「现在是不是主线行情、哪个板块还能延续、哪个该退」：结构判定、板块前瞻、后验回填和 AI 结论都在这一页，判定输入只有全板块日快照。</div>' +
    '</div><div class="page-actions">' +
      '<label class="mi-date-pick"><span class="sr-only">研判日期</span><select class="input" id="mi-date">' + opts + '</select></label>' +
      '<button class="btn sm" data-action="mi-step" data-d="-1" ' + (i <= 0 ? 'disabled' : '') + '>' + icon('arrow', 'sm') + '前一交易日</button>' +
      '<button class="btn sm" data-action="mi-step" data-d="1" ' + (i >= dates.length - 1 ? 'disabled' : '') + '>后一交易日' + icon('arrow', 'sm') + '</button>' +
      '<button class="btn sm" data-action="mi-run-regime"' + (run.regime ? ' disabled' : '') + '>' + icon('workflow', 'sm') + '跑行情结构</button>' +
      '<button class="btn sm" data-action="mi-run-verify">' + icon('check', 'sm') + '回填验证</button>' +
      '<button class="btn primary sm" data-action="mi-run-intel"' + (run.intel ? ' disabled' : '') + '>' + icon('agent', 'sm') +
        (state.miIntelBusy ? '研判中…' : '立即研判（后台）') + '</button>' +
      '<button class="btn sm" data-action="mi-refresh">' + icon('rotate', 'sm') + '刷新</button>' +
    '</div></div>' +
    '<div class="cp-toolbar"><div class="cp-chips">' + chips + '</div>' +
      '<span class="spacer"></span>' +
      '<button class="btn link xs" data-nav="#/candidates">候选池 ' + icon('arrow', 'sm') + '</button>' +
      '<button class="btn link xs" data-nav="#/paper">AI 模拟操盘 ' + icon('arrow', 'sm') + '</button></div>' +
    miConclusion(i, rg, intel) + miReadiness(i) + boards +
    '<div class="mi-body">' + body + '</div>' + miLogStrip();
}

/* ----- 看板一：行情结构与三窗口前瞻 ----- */
function miBoardRegime(i, rg, run) {
  if (!rg) {
    return '<div class="card"><div class="card-title"><h3>' + esc(miDate()) + ' 没有结构判定</h3>' +
        '<span class="hint">' + esc(miDates()[i]) + ' 的全板块快照在，判定结果不在</span></div>' +
      '<div class="empty-list"><strong>这一天 15:40 的行情结构任务没有产出记录</strong>' +
        '常见原因：箱位接口超时把整条判定带停、当日快照晚于任务时间、或该日期是回填前的历史日。<br>可以直接在页面补跑一轮（原型内本地计算），正式系统需要后端补一个手动跑 C′ 的接口。</div>' +
      '<div class="row mi-actions">' + miRunBtns(i, run) + '</div>' +
      '<div class="cap-note" style="margin-top:14px">' + icon('info') + '<div><b>落地缺口：</b>页面按钮「刷新行情结构」实际调的是 D′ 板块前瞻接口，' +
        '结构记录缺失时后端直接返回「行情结构预测不存在」。要真能补跑，需要新增 <span class="mono">POST /market/sector-regime/run</span>。</div></div></div>';
  }
  const e = rg.evidence;
  const fcs = miForecasts(i, rg);
  const h = ['t1', 't3', 't5'].indexOf(state.miHorizon) >= 0 ? state.miHorizon : 't1';
  const metrics = [
    ['龙头连续进前五', e.leader_streak_max_10d + ' 天', '≥3 天才算有主线', '阈值：连续 3 个交易日排在涨幅前五', e.leader_streak_max_10d >= 3],
    ['前三板块 20 日留存', e.top3_persistence_20d == null ? '—' : Math.round(e.top3_persistence_20d * 100) + '%', '≥60% 才算抱团', '今天前三名在过去 20 个交易日里，至少一个还在前五的天数占比', (e.top3_persistence_20d || 0) >= 0.6],
    ['近三日榜面换手', e.top5_churn_3d == null ? '—' : e.top5_churn_3d.toFixed(2), '≥0.6 判轮动', '1 − 相邻两日前五重合数 / 5，取最近三对平均', (e.top5_churn_3d || 0) >= 0.6],
    ['广度扩张', e.breadth_expansion_10d == null ? '—' : e.breadth_expansion_10d.toFixed(2), '辅助证据', '前五板块上涨家数均值对比两日前', null],
    ['量比确认', e.volume_confirm_3d == null ? '—' : e.volume_confirm_3d.toFixed(2), '>0.2 才算放量', '前五板块量比均值 − 两日前均值', (e.volume_confirm_3d || 0) > 0.2],
    ['前五 60 日箱位中位数', e.box_position_median_60d == null ? '—' : Math.round(e.box_position_median_60d * 100) + '%', '≥70% 位置偏高', '辅助标注：取数超时按缺失处理，不参与结构判定', (e.box_position_median_60d || 0) >= 0.7],
    ['判定窗口', e.window_days + ' 个交易日', '需 ≥60', '库内快照 68 个交易日，按当日可取窗口计算', !e.data_insufficient]
  ];
  const horizons = [['t1', 'T+1 次日'], ['t3', 'T+3 三日'], ['t5', 'T+5 五日']].map((x) =>
    '<button class="seg-item ' + (h === x[0] ? 'active' : '') + '" data-action="mi-horizon" data-h="' + x[0] + '">' + x[1] +
    '<span class="seg-count">' + MI_BIAS_LABEL[rg['forward_bias_' + x[0]]] + '</span></button>').join('');
  const watch = fcs.filter((f) => f.continuation_prob != null && f.continuation_prob >= 0.6 && f.exhaustion_risk < 0.6)
    .map((f) => f.sector);
  const risky = fcs.filter((f) => f.chase_risk >= 0.6).map((f) => f.sector);
  const sw = fcs.filter((f) => f.switch_candidate).map((f) => f.sector);
  const rows = fcs.map((f) => {
    return '<tr class="clickable" role="button" tabindex="0" data-action="mi-sector" data-s="' + esc(f.sector) + '">' +
      '<td class="mono">' + f.rank_no + '</td>' +
      '<td><span class="cp-name">' + esc(f.sector) + '</span>' + (f.sector === e.leader_streak_sector ? ' ' + tag('本轮龙头', 'gold') : '') + '</td>' +
      '<td class="mono">' + miPctCell(miDay(i).rows[f.rank_no - 1] && miDay(i).rows[f.rank_no - 1].chg) + '</td>' +
      '<td>' + miProb(f.continuation_prob) + '</td>' +
      '<td>' + miRisk(f.exhaustion_risk) + '</td>' +
      '<td>' + miRisk(f.chase_risk) + '</td>' +
      '<td>' + miBias(f['forward_bias_' + h]) + '</td>' +
      '<td>' + miSectorTag(f.sector_tag) + '</td>' +
      '<td class="mono">' + (f.box == null ? '<span class="dim">缺失</span>' : Math.round(f.box * 100) + '%') + '</td>' +
      '<td class="mono">' + f.streak + '</td>' +
      '<td>' + miCausalCell(f) + '</td>' +
      '<td>' + (f.falsified ? tag('反证已触发', 'red') : f.emotion_only ? tag('情绪票', 'gold') : '<span class="dim">—</span>') + '</td></tr>';
  }).join('');
  const acc = miAccuracy(i);
  const ver = miVerify(i, rg, fcs);
  return '<div class="grid-2 mi-top-grid">' +
      '<div class="card mi-big"><div class="card-title"><h3>结构定性</h3><span class="hint">' + esc(miDate()) + ' · 收盘后自动判定</span></div>' +
        '<div class="mi-verdict ' + rg.current_regime + '"><div><span class="mi-verdict-main">' + MI_REGIME_LABEL[rg.current_regime] + '</span>' +
          '<span class="mi-verdict-stage">' + MI_STAGE_LABEL[rg.regime_stage] + '</span></div>' +
          '<div class="mi-verdict-right"><div class="metric-label">结构置信度</div><div class="metric-value ' + (rg.regime_confidence >= 0.8 ? 'up' : rg.regime_confidence >= 0.5 ? '' : 'down') + '">' +
            Math.round(rg.regime_confidence * 100) + '%</div></div></div>' +
        '<p class="mi-why">' + miStageWhy(rg) + '</p>' +
        '<div class="seg mi-hor-seg">' + horizons + '</div>' +
        '<div class="cap-note' + (e.data_insufficient ? ' warn' : '') + '">' + icon('info') + '<div>' +
          (e.data_insufficient ? '<b>输入不足 60 个交易日</b>：置信度按规则压到 20%，只能当方向参考。' : '') +
          '箱位中位数只是位置标注：前五里有 ' + e.box_missing_count + ' 个板块本轮没取到箱位，缺失不会推翻结构结论，但该板块的延续概率会留空。' +
          '</div></div></div>' +
      '<div class="card"><div class="card-title"><h3>判定用到的六个数</h3><span class="hint">口径与阈值一起给，可对着快照核</span></div>' +
        '<div class="table-wrap"><table class="mi-metrics"><thead><tr><th>指标</th><th>当前值</th><th>阈值</th><th>口径</th><th>达标</th></tr></thead><tbody>' +
        metrics.map((m) => '<tr><td>' + esc(m[0]) + '</td><td class="mono"><b>' + esc(m[1]) + '</b></td><td class="dim">' + esc(m[2]) + '</td>' +
          '<td class="small muted">' + esc(m[3]) + '</td><td>' + (m[4] == null ? '<span class="dim">辅助</span>' : m[4] ? tag('达标', 'green') : tag('未达', 'mute')) + '</td></tr>').join('') +
        '</tbody></table></div></div>' +
    '</div>' +
    '<div class="card"><div class="card-title"><h3>今日榜面读数</h3><span class="hint">点任意一行看这个板块的完整链路</span></div>' +
      '<div class="mi-picks">' +
        '<div class="mi-pick"><span class="mi-pick-k">延续概率达标（≥60%）</span><span class="mi-pick-v">' + (watch.length ? watch.map((s) => '<button class="rule-chip" data-action="mi-sector" data-s="' + esc(s) + '">' + esc(s) + '</button>').join('') : '<span class="dim">没有</span>') + '</span></div>' +
        '<div class="mi-pick"><span class="mi-pick-k">追高风险（≥60%）</span><span class="mi-pick-v">' + (risky.length ? risky.map((s) => '<button class="rule-chip" data-action="mi-sector" data-s="' + esc(s) + '">' + esc(s) + '</button>').join('') : '<span class="dim">没有</span>') + '</span></div>' +
        '<div class="mi-pick"><span class="mi-pick-k">潜在切换方向</span><span class="mi-pick-v">' + (sw.length ? sw.map((s) => '<button class="rule-chip" data-action="mi-sector" data-s="' + esc(s) + '">' + esc(s) + '</button>').join('') : '<span class="dim">本轮没有给出切换候选</span>') + '</span></div>' +
      '</div></div>' +
    '<div class="card"><div class="card-title"><h3>板块三窗口前瞻（涨幅前十）</h3>' +
        '<span class="hint">当前窗口 ' + MI_BIAS_LABEL[rg['forward_bias_' + h]] + ' · 延续 = 0.35 前十日留存 + 0.20 量比贴 1 + 0.20 连续天数 + 0.15 广度 + 0.10 位置</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>名次</th><th>板块</th><th>当日涨幅</th><th>延续概率</th><th>退潮风险</th><th>追高风险</th>' +
        '<th>' + (h === 't1' ? 'T+1' : h === 't3' ? 'T+3' : 'T+5') + ' 倾向</th><th>板块标签</th><th>60日箱位</th><th>连续前五</th><th>原因硬度</th><th>提示</th></tr></thead>' +
        '<tbody>' + (rows || '<tr><td colspan="12" class="dim">没有前瞻记录</td></tr>') + '</tbody></table></div>' +
      '<div class="cap-note">' + icon('info') + '<div>「原因硬度」取当日板块归因置信度：≥75% 高硬度、45–75% 中等、<45% 低硬度。<b>只有当日归因参与前瞻修正</b>（±0.05），' +
        '旧日期的归因只作背景显示，不会拿来改今天分数——避免用上周的理由解释今天的涨幅。</div></div></div>' +
    miVerifyCard(ver) + miAccuracyCard(acc) +
    '<div class="card"><div class="card-title"><h3>结构判定的已知毛病</h3><span class="hint">对着后端代码核过的，正式落地要修</span></div>' +
      '<div class="stack">' + MI_REGIME_GAPS.map((g) => '<div class="mi-gap"><b>' + esc(g[0]) + '</b><p>' + esc(g[1]) + '</p></div>').join('') + '</div></div>';
}
const MI_SECTOR_TAG_LABEL = {
  mainline_seed: ['主线种子', 'green'], fade_warn: ['退潮预警', 'red'], accelerate_warn: ['加速追高', 'gold'],
  low_buy: ['中低位可关注', 'blue'], one_day_fly: ['一日游', 'mute'], none: ['—', 'mute']
};
function miSectorTag(t) {
  const m = MI_SECTOR_TAG_LABEL[t] || MI_SECTOR_TAG_LABEL.none;
  return m[0] === '—' ? '<span class="dim">—</span>' : tag(m[0], m[1]);
}
/* 缺失标记在 causal 对象里，不在前瞻行顶层：读错会把每一行都显示成「原因缺失 0%」 */
function miCausalOf(f) { return (f && f.causal) || {}; }
function miCausalMissing(f) { const c = miCausalOf(f); return !!c.causal_missing || c.confidence == null; }
function miCausalCell(f) {
  const c = miCausalOf(f);
  if (miCausalMissing(f)) {
    return tag('当日归因缺失', 'mute') + (c.source_trade_date ? ' <span class="dim small">最近 ' + esc(c.source_trade_date) + '，只作背景</span>' : '');
  }
  const band = miBand(c.confidence, false);
  return band.label + ' ' + tag(Math.round(c.confidence * 100) + '%', band.tone);
}
const MI_BAND_CN = { high: '高', medium: '中', low: '低', missing: '当日无归因' };
function miVerifyCard(ver) {
  const rows = ver.map((v) => {
    const r = v.miss_reason === 'data_insufficient';
    return '<tr><td>' + (v.verify_horizon === 't1' ? 'T+1 次日' : v.verify_horizon === 't3' ? 'T+3 三日' : 'T+5 五日') + '</td>' +
      '<td>' + MI_BIAS_LABEL[v.prediction] + '</td>' +
      '<td>' + (v.verify_date ? '<span class="mono">' + esc(v.verify_date) + '</span>' : '<span class="dim">未到期</span>') + '</td>' +
      '<td>' + (v.regime_hit == null ? '<span class="dim">口径需 ≥2 日窗口</span>' : v.regime_hit ? tag('结构命中', 'green') : tag('结构未命中', 'red')) + '</td>' +
      '<td>' + (v.mainline_hit == null ? '<span class="dim">未判定</span>' : v.mainline_hit ? tag('方向命中', 'green') : tag('方向错了', 'red')) + '</td>' +
      '<td class="mono">' + (v.top5_continue_rate == null ? '—' : Math.round(v.top5_continue_rate * 100) + '%') + '</td>' +
      '<td class="small muted">' + esc(miMissReason(v)) + '</td></tr>';
  }).join('');
  const cr = ver[0].detail.causal_review;
  return '<div class="card"><div class="card-title"><h3>这一轮的后验回填</h3>' +
      '<span class="hint">用预测日之后的真实行情回看：不猜，到期才算得出命中</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>窗口</th><th>当时判断</th><th>验证日</th><th>结构后验</th><th>方向后验</th><th>前五留存</th><th>没命中的原因</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>' +
      '<div class="kv mi-causal-review"><dt>归因复盘</dt><dd>' + esc(cr.sector || '—') + ' · 当时原因硬度 ' + esc(MI_BAND_CN[cr.band] || cr.band) +
        (cr.confidence != null ? '（' + Math.round(cr.confidence * 100) + '%）' : '') +
        ' · 市场验证 <b>' + miCausalStatus(cr.status) + '</b>' + (cr.gaps && cr.gaps.length ? ' · 缺：' + esc(cr.gaps.join('、')) : '') + '</dd></div>' +
      '<div class="cap-note">' + icon('info') + '<div>「结构后验」的口径很严：后验窗口内每一天都要有至少三个板块留在前五，否则后验结构就不是主线。' +
        '所以主线判断的命中率天然偏低，看的时候连着留存率一起看，不要单看命中百分比。</div></div></div>';
}
function miCausalStatus(s) {
  return { awaiting_market_verification: '等市场验证', market_validated: '已被市场验证', market_not_validated: '未被市场验证', causal_missing: '当日没有归因，不参与复盘' }[s] || s || '—';
}
function miMissReason(v) {
  if (v.miss_reason === 'data_insufficient') {
    return '后验窗口还差 ' + v.missing_days + ' 个交易日（需要 ' + v.detail.required_days + ' 日，实际 ' + v.detail.actual_days + ' 日）';
  }
  if (v.prediction === 'uncertain' || v.miss_reason === 'uncertain') return '当时判断就是「不确定」，不计命中也不计未命中';
  if (!v.miss_reason) return '命中：龙头 ' + esc(v.detail.mainline_sector || '—') + ' 区间累计 ' + (v.detail.mainline_change_sum == null ? '—' : v.detail.mainline_change_sum.toFixed(1) + '%') +
    (v.detail.switch_sector ? '，切换标的 ' + esc(v.detail.switch_sector) + ' ' + (v.detail.switch_change_sum == null ? '—' : v.detail.switch_change_sum.toFixed(1) + '%') : '');
  return '未命中：后验结构 ' + (v.detail.posterior_regime ? MI_REGIME_LABEL[v.detail.posterior_regime] : '样本不足') +
    '，龙头 ' + esc(v.detail.mainline_sector || '—') + ' 区间累计 ' + (v.detail.mainline_change_sum == null ? '—' : v.detail.mainline_change_sum.toFixed(1) + '%');
}
function miAccuracyCard(acc) {
  const rows = acc.windows.map((w) => {
    const g = {};
    w.groups.forEach((x) => { g[x.regime] = x; });
    const cell = (x) => !x || !x.sample_count ? '<span class="dim">无样本</span>' :
      '<div class="mi-acc-cell"><span class="' + ((x.regime_hit_rate || 0) >= 0.5 ? 'ok-t' : 'bad-t') + '">' + Math.round((x.regime_hit_rate || 0) * 100) + '%</span>' +
      '<span class="dim mono">n=' + x.sample_count + '</span>' +
      '<span class="small muted">留存 ' + (x.top5_continue_rate == null ? '—' : Math.round(x.top5_continue_rate * 100) + '%') +
      ' · 方向 ' + (x.mainline_hit_rate == null ? '—' : Math.round(x.mainline_hit_rate * 100) + '%') + '</span></div>';
    return '<tr><td><b>' + esc(w.label) + '</b><div class="small muted mono">' + esc(w.start_date) + ' ~ ' + esc(w.end_date) + '</div></td>' +
      '<td class="mono">' + w.sample_count + (w.pending ? ' <span class="dim">+' + w.pending + ' 待验证</span>' : '') + '</td>' +
      '<td>' + cell(g.mainline) + '</td><td>' + cell(g.rotation) + '</td><td>' + cell(g.chaos) + '</td></tr>';
  }).join('');
  const bands = acc.windows[1].causal_groups.map((b) =>
    '<tr><td>' + (b.band === 'missing' ? '当日无归因' : esc(b.label) + '硬度') + '</td><td class="mono">' + b.sample_count + '</td>' +
      '<td class="mono">' + (b.regime_hit_rate == null ? '—' : Math.round(b.regime_hit_rate * 100) + '%') + '</td>' +
      '<td class="mono">' + (b.top5_continue_rate == null ? '—' : Math.round(b.top5_continue_rate * 100) + '%') + '</td>' +
      '<td class="mono">' + (b.mainline_hit_rate == null ? '—' : Math.round(b.mainline_hit_rate * 100) + '%') + '</td></tr>').join('');
  const min = Math.min.apply(null, acc.windows.map((w) => w.sample_count));
  return '<div class="grid-2">' +
    '<div class="card"><div class="card-title"><h3>历史准确率</h3><span class="hint">按判定日统计，分母只算已到期的窗口</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>窗口</th><th>样本</th><th>主线行情</th><th>轮动行情</th><th>混沌行情</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      (min < 10 ? '<div class="cap-note warn">' + icon('alert') + '<div><b>样本太少：</b>最少的一组只有 ' + min + ' 条已到期判定，这个百分比随时会跳。' +
        '原型只保留了 22 个交易日的快照（正式库 68 日），「近 30 日 / 近 90 日」的窗口长度已经到边界，不要拿它当能力结论。</div></div>' : '') + '</div>' +
    '<div class="card"><div class="card-title"><h3>按原因硬度复盘</h3><span class="hint">近 30 日：硬证据支撑的判断，命中是否真的更高</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>归因硬度</th><th>样本</th><th>结构命中</th><th>前五留存</th><th>方向命中</th></tr></thead><tbody>' + bands + '</tbody></table></div>' +
      '<div class="cap-note">' + icon('info') + '<div>这张表是判断「值不值得继续让归因参与修正」的依据：如果高硬度组没有明显更好，就不该给它调分权重。</div></div></div></div>';
}

/* ----- 看板二：市场判定依据（归因与因果闭环） ----- */
function miBoardBasis(i, run) {
  const date = miDates()[i];
  const recs = MI_LAUNCH[date] || [];
  const fcs = miForecasts(i);
  if (!recs.length) {
    return '<div class="card"><div class="card-title"><h3>板块启动归因</h3><span class="hint">每个板块的「为什么涨」：结论 + 可回指证据</span></div>' +
      '<div class="empty-list"><strong>' + esc(date) + ' 没有板块归因</strong>' +
        '没有归因时，前瞻只按技术面公式算，原因硬度显示「当日归因缺失」，不会拿别的日期的理由来修正今天分数。</div>' +
      (fcs.length ? '<div class="cap-note accent">' + icon('info') + '<div>下面这几条是本轮真正参与前瞻的板块（都没有当日归因）：' +
        fcs.slice(0, 5).map((f) => esc(f.sector)).join('、') + '。正式系统里这一步会先跑归因再跑前瞻。</div></div>' : '') + '</div>';
  }
  const mode = state.miChainMode === 'time' ? 'time' : 'chain';
  return '<div class="cp-toolbar"><div class="seg">' +
      '<button class="seg-item ' + (mode === 'chain' ? 'active' : '') + '" data-action="mi-chain-mode" data-m="chain">证据链</button>' +
      '<button class="seg-item ' + (mode === 'time' ? 'active' : '') + '" data-action="mi-chain-mode" data-m="time">按时间</button></div>' +
      '<span class="spacer"></span><span class="hint">' + recs.length + ' 条当日归因 · 置信度 ≥75% 才加 0.05 延续分</span></div>' +
    '<div class="stack">' + recs.map((r) => miLaunchCard(i, r, mode, fcs)).join('') + '</div>' +
    '<div class="card"><div class="card-title"><h3>本轮没有归因的板块</h3><span class="hint">榜单前十里剩下的那些</span></div>' +
      '<div class="mi-picks"><div class="mi-pick"><span class="mi-pick-k">无当日归因</span><span class="mi-pick-v">' +
      (fcs.length ? fcs.filter(miCausalMissing).map((f) => '<button class="rule-chip" data-action="mi-sector" data-s="' + esc(f.sector) + '">' + esc(f.sector) + '</button>').join('') : '<span class="dim">先跑行情结构</span>') +
      '</span></div></div>' +
      '<div class="cap-note">' + icon('info') + '<div>它们的前瞻分数只反映技术面；页面上会一直显示「当日归因缺失」而不是留空，避免看上去像已经解释过了。</div></div></div>';
}
function miLaunchCard(i, r, mode, fcs) {
  const f = fcs.filter((x) => x.sector === r.sector)[0] || null;
  const band = miBand(r.confidence, false);
  const key = 'launch:' + r.sector;
  const full = state.miExpand[key];
  const tags = String(r.tags || '').split(',').filter(Boolean);
  return '<div class="card mi-launch"><div class="card-title"><h3><button class="btn link" data-action="mi-sector" data-s="' + esc(r.sector) + '">' +
      esc(r.sector) + ' ' + icon('arrow', 'sm') + '</button></h3>' +
      '<span class="spacer"></span>' + tag('持续 ' + r.days + ' 天', 'mute') + ' ' + tag('原因硬度 ' + band.label, band.tone) +
      ' ' + tag('置信度 ' + Math.round(r.confidence * 100) + '%', band.tone) + '</div>' +
      '<div class="mi-tags">' + tags.map((t) => '<span class="rule-chip ' + (t === 'emotion_only' || t === '传闻' ? 'warn' : '') + '">' +
        esc({ emotion_only: '只有情绪', 传闻: '传闻未证实', 订单验证: '有订单验证', 持续: '持续性已达标' }[t] || t) + '</span>').join('') + '</div>' +
      '<p class="mi-text' + (full ? ' full' : '') + '">' + esc(r.text) + '</p>' +
      '<button class="btn link xs" data-action="mi-expand" data-k="' + esc(key) + '">' + (full ? '收起' : '看完整归因') + '</button>' +
      (r.cap_reason ? '<div class="cap-note"><div class="icon">' + icon('info') + '</div><div><b>置信度为什么是这个数：</b>' + esc(r.cap_reason) + '</div></div>' : '') +
      '<div class="mi-cols">' +
        '<div><div class="audit-label">证据分层</div>' +
          '<div class="table-wrap"><table class="mi-causal"><thead><tr><th>层</th><th>主张</th><th>证据级</th><th>时间关系</th><th>因果判定</th></tr></thead><tbody>' +
          (r.causal || []).map((c) => '<tr><td>' + esc(c.layer) + '</td><td class="small">' + esc(c.claim) + '</td><td>' + miLevel(c.level) + '</td>' +
            '<td class="dim small">' + esc(c.align) + '</td><td class="small">' + esc(miCauseLabel(c.cause)) + '</td></tr>').join('') +
          '</tbody></table></div></div>' +
        '<div><div class="audit-label">' + (mode === 'time' ? '取证时间线' : '证据链') + '</div>' +
          (mode === 'time' ? '<div class="timeline">' + (r.chain || []).map((c, k) =>
            '<div class="tl-item"><div class="tl-dot"></div><div class="tl-body"><div class="tl-head"><b>' + esc(c.key) + '</b>' +
            '<span class="tl-time">' + esc(c.source) + ' · 第 ' + (k + 1) + ' 步</span></div><div class="small muted">' + esc(c.text) + '</div></div></div>').join('') + '</div>'
            : '<div class="mi-chain-list">' + (r.chain || []).map((c, k) =>
              '<div class="mi-chain-row"><span class="mi-chain-no">' + (k + 1) + '</span><div><b>' + esc(c.key) + '</b>' +
              '<span class="dim small"> · ' + esc(c.source) + '</span><p class="small muted">' + esc(c.text) + '</p></div></div>').join('') +
              (r.transmission ? '<div class="mi-trans">' + esc(r.transmission) + '</div>' : '') + '</div>') +
          '</div>' +
      '</div>' +
      '<div class="grid-2">' +
        '<div class="mi-block"><div class="audit-label">产业传导链条</div><p class="small">' + esc(r.transmission || '未提供：只有情绪，没有可回指的传导路径') + '</p></div>' +
        '<div class="mi-block"><div class="audit-label">资金行为验证</div><dl class="kv mi-kv">' +
          Object.keys(r.capital || {}).map((k) => '<dt>' + esc({ main_net_in_3d: '主力净流入(3日)', north_bound: '北向', margin: '融资余额', turnover: '换手率' }[k] || k) +
            '</dt><dd>' + esc(r.capital[k]) + '</dd>').join('') + '</dl></div>' +
      '</div>' +
      '<div class="mi-falsify"><div class="audit-label">反证条件（出现就该改判断）</div>' +
        '<div class="table-wrap"><table class="mi-fal"><thead><tr><th>窗口</th><th>条件</th></tr></thead><tbody>' +
        [['t1', 'T+1 次日'], ['t3', 'T+3 三日'], ['t5', 'T+5 五日']].map((x) =>
          '<tr><td>' + x[1] + '</td><td class="small">' + esc((r.falsify || {})[x[0]] || '未提供') + '</td></tr>').join('') +
        '</tbody></table></div>' +
        (r.falsify && r.falsify.triggered ? '<div class="cap-note warn">' + icon('alert') +
          '<div><b>反证条件已触发：</b>这条理由不再支撑延续判断，前瞻里的「延续 / 主线确认」标签被撤掉，改按不确定或切换处理；退潮风险与追高风险各加 0.05。' +
          '判定只看证据里那个明确布尔标记，不从文字里猜。</div></div>' : '<div class="cap-note"><div class="icon">' + icon('check') +
          '</div><div>反证条件未触发。触发状态由后验回填写入，不由模型自由发挥。</div></div>') +
      '</div>' +
      (f ? '<div class="mi-link-row"><span class="hint">这一条对前瞻的净影响：</span>' +
        (f.causal_adjustment == null ? '<span class="dim">当日归因缺失或置信度在中段，未修正分数</span>'
          : '<span class="' + (f.causal_adjustment > 0 ? 'ok-t' : 'bad-t') + '">' + (f.causal_adjustment > 0 ? '+' : '') + (f.causal_adjustment * 100).toFixed(0) +
            ' 延续分</span><span class="dim">（技术面 ' + Math.round((f.evidence.technical_continuation_prob || 0) * 100) + '% → 修正后 ' +
            Math.round((f.continuation_prob || 0) * 100) + '%）</span>') +
        '<span class="spacer"></span><button class="btn link xs" data-action="mi-sector" data-s="' + esc(r.sector) + '">看板块链路 ' + icon('arrow', 'sm') + '</button></div>' : '') +
    '</div>';
}

/* ----- 看板三：核心矛盾 ----- */
function miBoardConflict(i, rg, intel) {
  const fcs = miForecasts(i);
  const triggered = fcs.filter((f) => f.falsified);
  const emotional = fcs.filter((f) => f.emotion_only);
  const missing = fcs.filter(miCausalMissing);
  const posHigh = fcs.filter((f) => f.box != null && f.box >= 0.7);
  const date = miDates()[i];
  const launch = MI_LAUNCH[date] || [];
  if (!intel) {
    return '<div class="card"><div class="card-title"><h3>核心矛盾</h3><span class="hint">这一段本来由 16:20 的 AI 研判写</span></div>' +
      '<div class="empty-list"><strong>' + esc(date) + ' 的 AI 研判还没生成</strong>下面只给纯代码能确定的矛盾点：位置、反证与归因缺口。</div>' +
      miHardConflicts(rg, posHigh, triggered, emotional, missing) + '</div>';
  }
  const paras = String(intel.core_conflict || '').split('\n').filter(Boolean);
  return '<div class="card"><div class="card-title"><h3>AI 认为这一轮最纠结的点</h3>' +
      '<span class="hint">AI 原文照贴，页面不改写措辞</span></div>' +
      '<div class="stack">' + paras.map((p, k) => '<div class="mi-conflict"><span class="mi-conflict-no">' + (k + 1) + '</span><p>' + esc(p) + '</p></div>').join('') + '</div></div>' +
    miHardConflicts(rg, posHigh, triggered, emotional, missing) +
    '<div class="card"><div class="card-title"><h3>反证条件是否被碰到</h3><span class="hint">代码只认证据里的明确布尔标记</span></div>' +
      (launch.length ? '<div class="table-wrap"><table><thead><tr><th>板块</th><th>T+1 反证</th><th>T+5 反证</th><th>状态</th></tr></thead><tbody>' +
        launch.map((r) => '<tr><td><button class="btn link" data-action="mi-sector" data-s="' + esc(r.sector) + '">' + esc(r.sector) + '</button></td>' +
          '<td class="small">' + esc((r.falsify || {}).t1 || '未提供') + '</td><td class="small">' + esc((r.falsify || {}).t5 || '未提供') + '</td>' +
          '<td>' + ((r.falsify || {}).triggered ? tag('已触发', 'red') : tag('未触发', 'mute')) + '</td></tr>').join('') + '</tbody></table></div>'
        : '<div class="empty-list">本轮没有归因，反证条件为空。</div>') + '</div>';
}
function miHardConflicts(rg, posHigh, triggered, emotional, missing) {
  const rows = [];
  if (rg && rg.current_regime === 'mainline' && posHigh.length >= 3) {
    rows.push(['位置已经上来了', '前十里有 ' + posHigh.length + ' 个板块 60 日箱位 ≥70%：' + posHigh.map((f) => f.sector).join('、') +
      '。结构与证据还在，但容错变小——判断从「跟不跟」变成「什么价跟」。']);
  }
  if (triggered.length) {
    rows.push(['有理由被自己的反证推翻了', triggered.map((f) => f.sector).join('、') + '：归因里写的反证条件已经出现，这些板块的「延续 / 主线确认」标签被撤销，改按不确定或切换处理。']);
  }
  if (emotional.length) {
    rows.push(['情绪票混在主线里', emotional.map((f) => f.sector).join('、') + '：标记 emotion_only，只解释当天，不进 T+3/T+5 延续判断，板块标签降为「一日游」。']);
  }
  if (missing.length) {
    rows.push(['榜单上大半没有当日理由', missing.length + '/' + (missing.length + 1) + ' 以上的板块没有当日归因，它们的分数只有技术面，页面上不会伪装成已解释。']);
  }
  if (rg && rg.current_regime === 'chaos') {
    rows.push(['结构判不出来本身就是结论', '现在既没有连续三天在榜的龙头，榜面换手也没到轮动阈值，任何主线判断都可能第二天被推翻。这一轮的操作含义就是不做。']);
  }
  if (!rows.length) return '';
  return '<div class="card"><div class="card-title"><h3>纯代码能确定的矛盾点</h3><span class="hint">不依赖模型措辞，直接来自判定输入</span></div>' +
    '<div class="stack">' + rows.map((r) => '<div class="mi-conflict"><span class="mi-conflict-no">' + icon('alert', 'sm') + '</span><div><b>' + esc(r[0]) + '</b><p>' + esc(r[1]) + '</p></div></div>').join('') + '</div></div>';
}

/* ----- 看板四：板块量能信号 ----- */
function miBoardVolume(i, intel) {
  const vs = intel ? intel.volume_signal : miVolumeSignal(i);
  const fcs = miForecasts(i);
  const date = miDates()[i];
  const rows = (miDay(i).partial
    ? miDay(i).rows.map((r) => '<tr><td class="mono">' + r.rank + '</td><td>' + esc(r.sector) + '</td>' +
      '<td colspan="4" class="dim">这一天只有前五名名单，涨幅/量比/上涨家数未保留（原型只留了名单）</td><td class="mono">' +
      (miBox(r.sector, i) == null ? '—' : Math.round(miBox(r.sector, i) * 100) + '%') + '</td></tr>').join('')
    : miDay(i).rows.map((r) => {
      const f = fcs.filter((x) => x.sector === r.sector)[0] || null;
      return '<tr class="' + (f ? 'clickable' : '') + '"' + (f ? ' role="button" tabindex="0" data-action="mi-sector" data-s="' + esc(r.sector) + '"' : '') + '>' +
        '<td class="mono">' + r.rank + '</td><td><span class="cp-name">' + esc(r.sector) + '</span></td>' +
        '<td>' + miPctCell(r.chg) + '</td>' +
        '<td class="mono">' + (r.vol == null ? '—' : r.vol.toFixed(1)) + '</td>' +
        '<td class="mono">' + (r.up == null ? '—' : r.up + ' 家') + '</td>' +
        '<td class="mono">' + (f ? Math.round(f.top10_freq * 100) + '%' : '—') + '</td>' +
        '<td class="mono">' + (f && f.box != null ? Math.round(f.box * 100) + '%' : '<span class="dim">缺失</span>') + '</td></tr>';
    }).join(''));
  const miss = MI_BOX_MISSING.date === date ? MI_BOX_MISSING.sectors : [];
  return (vs.available ? '' : '<div class="pp-banner"><div class="pp-banner-line err">' + icon('alert', 'sm') +
      '<span><b>本轮板块量比没有取到</b>（akshare 东财接口未返回）。放量 / 缩量 / 极端量能全部按缺失处理，不用上一次的数值顶上；' +
      '这一轮的「量能成色」只能引用 AI 原文，不能作为判断依据。</span></div></div>') +
    '<div class="grid-3">' +
      '<div class="card mi-sig"><div class="card-title"><h3>放量板块（量比 ≥1.8）</h3></div>' +
        '<div class="mi-sig-body">' + (vs.available ? (vs['放量板块'] === '（无）' ? '<span class="dim">本轮没有</span>' : esc(vs['放量板块'])) : '<span class="dim">数据源未返回量比</span>') + '</div></div>' +
      '<div class="card mi-sig"><div class="card-title"><h3>缩量板块（量比 ≤0.8）</h3></div>' +
        '<div class="mi-sig-body">' + (vs.available ? (vs['缩量板块'] === '（无）' ? '<span class="dim">本轮没有</span>' : esc(vs['缩量板块'])) : '<span class="dim">数据源未返回量比</span>') + '</div></div>' +
      '<div class="card mi-sig"><div class="card-title"><h3>极端量能（量比 ≥2.3）</h3></div>' +
        '<div class="mi-sig-body">' + (vs.available ? (vs['极端量能'] ? esc(vs['极端量能']) : '<span class="dim">本轮没有</span>') : '<span class="dim">数据源未返回量比</span>') + '</div></div>' +
    '</div>' +
    '<div class="card"><div class="card-title"><h3>前五名量价分布</h3><span class="hint">' + esc(date) + ' 快照原值，可与行情软件逐行对</span></div>' +
      '<dl class="kv mi-kv"><dt>分布</dt><dd class="mono">' + esc(vs['分布']) + '</dd>' +
      (intel ? '<dt>AI 量能成色</dt><dd>' + esc(vs['量能成色'] || '本轮该字段为空') + '</dd>' +
        '<dt>主线结构</dt><dd>进攻 ' + esc(vs['主线结构'].attack || '未提供') + ' · 接力 ' + esc(vs['主线结构'].relay || '未提供') +
        ' · 退潮 ' + esc(vs['主线结构'].fade || '未提供') + '</dd>' : '') + '</dl></div>' +
    '<div class="card"><div class="card-title"><h3>60 日箱位与位置解读</h3>' +
        '<span class="hint">箱位 = 当前收盘价在过去 60 个交易日最高最低价区间的百分位</span></div>' +
      (miss.length ? '<div class="cap-note warn">' + icon('alert') + '<div><b>' + esc(miss.join('、')) + '</b>：' + esc(MI_BOX_MISSING.note) +
        '。箱位是辅助标注，取数超时只让这一格留空，结构判定和落库都不该被它拖停——正式代码里这条降级只写在板块前瞻那一步，结构判定那一步还会因为同一个异常整体失败。</div></div>' : '') +
      '<div class="table-wrap"><table><thead><tr><th>名次</th><th>板块</th><th>当日涨幅</th><th>量比</th><th>上涨家数</th><th>近10日在榜</th><th>60日箱位</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>' +
      (intel ? '<div class="stack mi-box-notes">' + Object.keys(intel.operative_meaning['箱位理解'] || {}).map((k) =>
        '<div class="mi-box-note"><button class="btn link" data-action="mi-sector" data-s="' + esc(k) + '">' + esc(k) + ' ' + icon('arrow', 'sm') + '</button>' +
        '<p>' + esc(intel.operative_meaning['箱位理解'][k]) + '</p></div>').join('') +
        (Object.keys(intel.operative_meaning['箱位理解'] || {}).length ? '' : '<div class="empty-list">本轮 AI 没有给箱位理解。</div>') + '</div>' : '') +
      '<div class="cap-note">' + icon('info') + '<div>箱位高不等于一定要退：' +
        '箱位只进「退潮风险」的 40% 和「追高风险」的 20%，量比与持续性不塌，主线判定不会单纯因为位置高被否。</div></div></div>';
}

/* ----- 看板五：操作含义 ----- */
function miBoardOperative(i, intel) {
  if (!intel) {
    return '<div class="card"><div class="card-title"><h3>操作含义</h3></div>' +
      '<div class="empty-list"><strong>本轮没有 AI 操作含义</strong>结构判定给出的三窗口倾向仍在「行情结构」看板，这里补的是把它翻成「该做什么」的那段话。</div>' +
      miBiasToAction(miRun(i).regime ? miRegime(i) : null) + '</div>';
  }
  const om = intel.operative_meaning || {};
  return '<div class="card"><div class="card-title"><h3>操作含义</h3><span class="hint">AI 写的操作含义，页面不改写</span></div>' +
      '<dl class="kv mi-kv">' + Object.keys(om).filter((k) => typeof om[k] !== 'object').map((k) =>
        '<dt>' + esc(k) + '</dt><dd>' + esc(om[k] || '未提供') + '</dd>').join('') +
        '<dt>箱位理解 / 个股验证</dt><dd>' + (Object.keys(om['箱位理解'] || {}).length || (om['个股验证'] || []).length
          ? '见下面两张卡，这里不重复展开' : '本轮 AI 没有给这两项') + '</dd></dl>' +
      miBiasToAction(miRun(i).regime ? miRegime(i) : null) + '</div>' +
    '<div class="card"><div class="card-title"><h3>主线板块内个股三维验证</h3>' +
      '<span class="hint">涨幅、量比、箱位三个维度合不合理，不看单看涨幅</span></div>' +
      ((intel.operative_meaning['个股验证'] || []).length ? '<div class="table-wrap"><table><thead><tr><th>个股</th><th>代码</th><th>当日涨幅</th><th>量比</th><th>60日箱位</th><th>三维判定</th><th>为什么</th></tr></thead><tbody>' +
        intel.operative_meaning['个股验证'].map((s) => '<tr><td><b>' + esc(s.name) + '</b></td><td class="mono dim">' + esc(s.code) + '</td>' +
          '<td>' + miPctCell(s.chg) + '</td><td class="mono">' + (s.vol == null ? '<span class="dim">未取到</span>' : s.vol.toFixed(1)) + '</td>' +
          '<td class="mono">' + (s.box == null ? '—' : s.box + '%') + '</td><td>' + miVerdict(s.verdict) + '</td>' +
          '<td class="small muted">' + esc(miStockWhy(s)) + '</td></tr>').join('') + '</tbody></table></div>'
        : '<div class="empty-list">本轮 AI 没有给个股验证。</div>') +
      '<div class="cap-note">' + icon('info') + '<div>「真强」= 涨幅、量比、箱位三者同向；「加速后段 / 放量滞涨」= 位置已在 90 分位以上，涨靠估值而不是业绩；' +
        '「假强」= 涨幅靠板块β，量比不配合。判定用词与正式页面一致，不新造标签。</div></div></div>' +
    '<div class="card"><div class="card-title"><h3>这些结论怎么用到操作上</h3><span class="hint">只到「方向」，不下单</span></div>' +
      '<div class="grid-3">' +
        '<div class="mi-use"><b>接力方向进候选池</b><p>把「主线种子 / 中低位可关注」的板块带到候选池，按板块筛一遍再决定要不要看个股。</p>' +
          '<button class="btn sm" data-nav="#/candidates">' + icon('arrow', 'sm') + '去候选池</button></div>' +
        '<div class="mi-use"><b>已在持仓的方向对不对</b><p>如果持仓板块本轮被判「退潮预警 / 加速追高」，去持仓监控看风险条，不在这页改持仓。</p>' +
          '<button class="btn sm" data-nav="#/holdings">' + icon('arrow', 'sm') + '去持仓监控</button></div>' +
        '<div class="mi-use"><b>AI 有没有按判断执行</b><p>模拟盘是唯一 AI 自己下单的地方，看它在这一轮结构下买了什么、事后复盘怎么说。</p>' +
          '<button class="btn sm" data-nav="#/paper">' + icon('arrow', 'sm') + '看模拟盘</button></div>' +
      '</div></div>';
}
function miStockWhy(s) {
  if (s.vol == null) return '量比缺失，只能看涨幅与箱位，判定保留但标注数据不足';
  if (s.verdict === '真强') return '量比 ' + s.vol.toFixed(1) + ' 有增量资金，箱位 ' + s.box + '% 未到极值，涨幅能落到量能上';
  if (s.verdict === '假强') return '量比 ' + s.vol.toFixed(1) + ' 没有配合，箱位 ' + s.box + '% 已在高位，涨幅来自板块β';
  return '量比 ' + s.vol.toFixed(1) + '，箱位 ' + s.box + '% 处于历史高分位，涨得快但位置已透支';
}
function miBiasToAction(rg) {
  if (!rg) return '<div class="cap-note"><div class="icon">' + icon('info') + '</div><div>没有结构判定，下面这三条倾向也无从给出。</div></div>';
  const map = {
    continue: '结构在延续：仓位优先给已经有硬证据的环节，跟随性补涨不作为建仓理由。',
    mainline_confirm: '五日口径是主线确认：可以分批参与，但加仓条件写在归因里（订单、公告、招标落地）。',
    switch: '倾向切换：不追老龙头，也不接第一天冒出来的题材，等新的连续在榜再做接力。',
    new_mainline_switch: '五日口径是新主线切换：把注意力从本轮龙头移开，去候选池按新板块筛。',
    fade: '倾向退潮：主线内部只做已证明业绩的部分，其余不加仓。',
    diverge: '三日口径是分歧：分歧期不做新开仓，等榜面重新收敛。',
    invalid_rotation: '五日口径判定这轮轮动无效：轮动行情里做切换，五日尺度大概率是错的。',
    uncertain: '判断就是不确定：不确定就是不动作，不要用「试试看」替代判断。'
  };
  return '<div class="mi-bias-acts">' + [['T+1 次日', rg.forward_bias_t1], ['T+3 三日', rg.forward_bias_t3], ['T+5 五日', rg.forward_bias_t5]].map((x) =>
    '<div class="mi-bias-act"><span class="mi-bias-k">' + x[0] + '</span>' + miBias(x[1]) + '<p>' + esc(map[x[1]] || '没有对应的动作口径') + '</p></div>').join('') + '</div>';
}

/* ----- 看板六：次日盯盘点 ----- */
function miBoardWatch(i, intel) {
  const date = miDates()[i];
  const nxt = MI_NEXT_HOT[date] || MI_NEXT_HOT[miDates()[Math.min(miDates().length - 1, i + 1)]] || [];
  const rg = miRun(i).regime ? miRegime(i) : null;
  const fcs = miForecasts(i);
  const seeds = fcs.filter((f) => f.sector_tag === 'mainline_seed' || f.switch_candidate);
  return (intel ? '<div class="card"><div class="card-title"><h3>明天开盘要盯的具体条件</h3>' +
        '<span class="hint">每条都写了「出现什么就改判断」，不是含糊的继续观察</span></div>' +
        '<div class="table-wrap"><table><thead><tr><th>盯什么</th><th>出现什么情况就改判断</th><th>下一步</th></tr></thead><tbody>' +
        Object.keys(intel.next_day_watch || {}).map((k) => '<tr><td><b>' + esc(k) + '</b></td><td class="small">' + esc(intel.next_day_watch[k]) + '</td>' +
          '<td>' + miWatchAction(intel.next_day_watch[k]) + '</td></tr>').join('') + '</tbody></table></div></div>'
      : '<div class="card"><div class="card-title"><h3>次日盯盘点</h3></div>' +
        '<div class="empty-list"><strong>' + esc(date) + ' 没有 AI 次日盯盘清单</strong>下面两条是纯代码给出的：本轮标签和「下一个风口」候选。</div></div>') +
    '<div class="card"><div class="card-title"><h3>下一个风口（前十之外的扩散候选）</h3>' +
      '<span class="hint">15:50 单独跑一批，不等 AI 归因，避免主线归因 5 分钟没出来时页面空白</span></div>' +
      (nxt.length ? '<div class="table-wrap"><table><thead><tr><th>排名</th><th>板块</th><th>热度</th><th>连续预热</th><th>可信度</th><th>与主线的传导距离</th><th>逻辑</th><th>必须出现什么</th></tr></thead><tbody>' +
        nxt.map((n) => '<tr><td class="mono">' + n.rank + '</td><td><button class="btn link" data-action="mi-sector" data-s="' + esc(n.sector) + '">' + esc(n.sector) + '</button></td>' +
          '<td class="mono">' + n.hot + '</td><td class="mono">' + n.days + ' 日</td>' +
          '<td>' + miProb(n.conf) + '</td>' +
          '<td>' + (n.trig.missing ? tag('传导关系缺失', 'gold') : esc(n.trig.dist) + ' <span class="dim mono">同源 ' + Math.round(n.trig.parent * 100) + '%</span>') + '</td>' +
          '<td class="small">' + esc(n.trig.logic) + '</td><td class="small muted">' + esc(n.trig.must) + '</td></tr>').join('') + '</tbody></table></div>'
        : '<div class="empty-list">这一天的「下一个风口」没有跑出来（15:50 任务未落库）。</div>') +
      '<div class="cap-note">' + icon('info') + '<div>可信度不到 45% 的候选不给建仓建议，只当观察名单；传导距离「未知」说明它和主线之间找不到可回指的产业关系，' +
        '这类票涨了也不该解释成主线扩散。</div></div></div>' +
    '<div class="grid-2">' +
      '<div class="card"><div class="card-title"><h3>本轮标签给的接力候选</h3></div>' +
        (seeds.length ? '<div class="mi-picks"><div class="mi-pick"><span class="mi-pick-k">种子 / 切换候选</span><span class="mi-pick-v">' +
          seeds.map((f) => '<button class="rule-chip" data-action="mi-sector" data-s="' + esc(f.sector) + '">' + esc(f.sector) + ' · ' +
            esc(MI_SECTOR_TAG_LABEL[f.sector_tag] ? MI_SECTOR_TAG_LABEL[f.sector_tag][0] : '切换候选') + '</button>').join('') + '</span></div></div>'
          : '<div class="empty-list">本轮没有给出主线种子或切换候选。</div>') + '</div>' +
      '<div class="card"><div class="card-title"><h3>研判日志</h3><span class="hint">本页跑批推进记录</span></div>' +
        ((state.miLog || []).length ? '<div class="mi-loglist">' + state.miLog.map((l) =>
          '<div class="mi-logrow"><span class="mono dim">' + esc(l.at) + '</span><span class="mono">' + esc(l.date) + '</span><span>' + esc(l.text) + '</span></div>').join('') + '</div>'
          : '<div class="empty-list">还没有在本页做过补跑。定时任务链路：15:35 快照 → 15:40 结构 → 15:45 前瞻 → 15:50 下一个风口 → 16:05 后验 → 16:20 AI 研判。</div>') + '</div>' +
    '</div>' +
    (rg ? '' : '<div class="cap-note warn">' + icon('alert') + '<div>这一天没有结构判定，「次日盯盘点」里的 T+1/T+3/T+5 倾向也是空的：先补跑行情结构，再谈明天盯什么。</div></div>');
}
function miWatchAction(text) {
  if (/跌破|跌出|转负|没有|未|证伪|不参与/.test(text)) return tag('触发就减仓 / 不参与', 'red');
  if (/落地|公告|连续|转正|为正/.test(text)) return tag('落地才继续加', 'green');
  return tag('继续观察', 'mute');
}

/* ----- 看板七：板块轮动归因 ----- */
function miBoardRotation(i, rg, run) {
  const date = miDates()[i];
  const patterns = MI_PATTERNS;
  const fcs = miForecasts(i);
  const churn = rg ? rg.evidence.top5_churn_3d : null;
  const state3 = rg ? (rg.current_regime === 'mainline' ? '主线' : rg.current_regime === 'rotation' ? '轮动' : '混沌') : '未知';
  const expl = {
    主线: '有一个板块连续排在涨幅前五，且前三板块 20 日留存过线，资金集中在同一条产业线上。',
    轮动: '榜面换手很快（近三日超过一半席位在换），但没有谁做出持续性：钱在板块之间搬，不在一个方向上聚。',
    混沌: '既没有连续在榜的龙头，也没快到能叫轮动的程度：每天的榜面更像资金单日选择，第二天不认账。',
    未知: '这一天没有结构判定，先补跑行情结构。'
  };
  const leaderChanges = (function () {
    const from = Math.max(0, i - 9);
    let n = 0;
    for (let k = from + 1; k <= i; k++) if (miTop(k, 1)[0] !== miTop(k - 1, 1)[0]) n += 1;
    return { n: n, days: i - from };
  })();
  return '<div class="grid-3">' +
      '<div class="card"><div class="card-title"><h3>轮动状态</h3></div><div class="metric-strip">' +
        '<div class="metric"><div class="metric-label">当前结构</div><div class="metric-value">' + esc(state3) + '</div><div class="metric-sub">' + esc(rg ? MI_STAGE_LABEL[rg.regime_stage] : '未判定') + '</div></div>' +
        '<div class="metric"><div class="metric-label">近三日榜面换手</div><div class="metric-value">' + (churn == null ? '—' : churn.toFixed(2)) + '</div><div class="metric-sub">阈值 0.60</div></div>' +
        '<div class="metric"><div class="metric-label">近 10 日榜首更换</div><div class="metric-value">' + leaderChanges.n + ' 次</div><div class="metric-sub">共 ' + leaderChanges.days + ' 个交易日</div></div>' +
      '</div><p class="small muted mi-why">' + esc(expl[state3]) + '</p></div>' +
      '<div class="card"><div class="card-title"><h3>本轮主切方向</h3><span class="hint">按快照现算</span></div>' +
        (rg ? '<dl class="kv mi-kv"><dt>龙头板块</dt><dd>' + esc(rg.evidence.leader_streak_sector || '没有连续在榜的板块') + '</dd>' +
          '<dt>今日前三</dt><dd>' + esc(miTop(i, 3).join('、')) + '</dd>' +
          '<dt>两日前前五</dt><dd>' + esc(miTop(Math.max(0, i - 2), 5).join('、')) + '</dd>' +
          '<dt>新挤进来的</dt><dd>' + esc(miTop(i, 5).filter((s) => miTop(Math.max(0, i - 2), 5).indexOf(s) < 0).join('、') || '没有') + '</dd>' +
          '<dt>掉出前五的</dt><dd>' + esc(miTop(Math.max(0, i - 2), 5).filter((s) => miTop(i, 5).indexOf(s) < 0).join('、') || '没有') + '</dd></dl>'
          : '<div class="empty-list">没有结构判定，主切方向算不出来。</div>') + '</div>' +
      '<div class="card"><div class="card-title"><h3>可延续板块</h3></div>' +
        (fcs.length ? '<div class="mi-picks"><div class="mi-pick"><span class="mi-pick-v">' +
          fcs.filter((f) => f['forward_bias_t1'] === 'continue').map((f) => '<button class="rule-chip" data-action="mi-sector" data-s="' + esc(f.sector) + '">' +
            esc(f.sector) + ' <span class="mono dim">' + Math.round(f.continuation_prob * 100) + '%</span></button>').join('') || '<span class="dim">本轮没有延续倾向达标的板块</span>' +
          '</span></div></div>' : '<div class="empty-list">先跑行情结构。</div>') +
        '<div class="cap-note"><div class="icon">' + icon('info') + '</div><div>可延续只按板块分数排，不代表可以买：追高风险与位置在「行情结构」看板的同一行里。</div></div></div>' +
    '</div>' +
    (run.rotation ? miRotationAi(date, i) : '<div class="card"><div class="card-title"><h3>轮动归因（AI 版）</h3>' +
      '<span class="hint">旧的轮动归因口径，单次要跑约 5 分钟</span></div>' +
      '<div class="empty-list"><strong>' + esc(date) + ' 的轮动归因还是空的</strong>正式页面这段一直是「等待回填」：它跑在另一条批里，没跟 16:20 研判合并，' +
        '所以出现「AI 研判有、轮动归因没有」的半程状态。<br>本页先用「下一个风口」和板块前瞻顶上，不让页面空着。</div>' +
      '<div class="row mi-actions">' + miRunBtns(i, run) + '</div></div>') +
    '<div class="card"><div class="card-title"><h3>多窗口规律</h3><span class="hint">3 / 10 / 20 / 60 日各自的轮动周期与主线，口径独立于当日结构判定</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>窗口</th><th>轮动周期(日)</th><th>生命周期均值</th><th>切换频率</th><th>放量后延续率</th><th>窗口内主线</th><th>涨幅斜率前三</th></tr></thead><tbody>' +
      ['3d', '10d', '20d', '60d'].map((k) => {
        const p = patterns[k];
        return '<tr><td><b>' + p.days + ' 日</b></td><td class="mono">' + p.rotation_cycle + '</td><td class="mono">' + p.lifecycle_avg_streak + '</td>' +
          '<td class="mono">' + p.switch_frequency.toFixed(2) + '</td><td class="mono">' + Math.round(p.volume_breakout_continuation * 100) + '%</td>' +
          '<td class="small">' + esc(p.mainline.join('、')) + '</td>' +
          '<td class="small">' + p.top_slopes.map((s) => esc(s.s) + ' <span class="mono dim">+' + s.v.toFixed(1) + '</span>').join('、') + '</td></tr>';
      }).join('') + '</tbody></table></div>' +
      '<div class="grid-3 mi-uses">' +
        '<div class="mi-use"><b>短周期（3 日）</b><p>切换频率 0.62：三天内换两次方向是常态。用它决定「隔几天复查一次」，不决定方向。</p></div>' +
        '<div class="mi-use"><b>中周期（10 / 20 日）</b><p>放量后延续率 55% 是四个窗口里最高的：突破当天有量，才值得拿过一周。</p></div>' +
        '<div class="mi-use"><b>长周期（60 日）</b><p>60 日主线只有光模块一个，说明这轮不是普涨，是单线行情——分散买题材等于摊薄。</p></div>' +
      '</div>' +
      '<div class="cap-note"><div class="icon">' + icon('info') + '</div><div><b>📌 关注重点：</b>切换频率随窗口变长单调下降（0.62 → 0.18），' +
        '意味着短线看到的「轮动」大多在 20 日尺度上不存在。用错窗口就会把噪音当方向。</div></div></div>';
}
function miRotationAi(date, i) {
  const fcs = miForecasts(i);
  const rows = fcs.slice(0, 6).map((f) => {
    const rec = (MI_LAUNCH[date] || []).filter((l) => l.sector === f.sector)[0];
    return '<tr class="clickable" role="button" tabindex="0" data-action="mi-sector" data-s="' + esc(f.sector) + '">' +
      '<td><b>' + esc(f.sector) + '</b><div class="small muted">' + (rec ? '持续 ' + rec.days + ' 天 · ' + esc(miBand(rec.confidence, false).label) + '硬度' : '当日归因缺失') + '</div></td>' +
      '<td class="small">' + esc(rec ? rec.text.slice(0, 80) + (rec.text.length > 80 ? '…' : '') : '没有 AI 评估，只有板块分数') + '</td>' +
      '<td>' + (rec ? '<button class="btn link xs" data-action="mi-expand" data-k="launch:' + esc(f.sector) + '">展开</button>' : '<span class="dim">未提供</span>') + '</td>' +
      '<td>' + miBias(f.forward_bias_t1) + '</td><td>' + miProb(f.continuation_prob) + '</td></tr>';
  }).join('');
  return '<div class="card"><div class="card-title"><h3>轮动归因（AI 版）</h3>' +
      '<span class="hint">' + esc(date) + ' 已回填 · 每个板块一条启动理由</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>板块</th><th>AI 评估</th><th>全文</th><th>T+1 倾向</th><th>延续概率</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<div class="cap-note"><div class="icon">' + icon('info') + '</div><div>这段文字只作解释，不进分数；真正改分数的是「当日归因置信度」（±0.05）和反证布尔标记。</div></div></div>';
}

/* ----- 看板八：原始返回 ----- */
function miBoardRaw(i, rg, intel, run) {
  const date = miDates()[i];
  const fcs = miForecasts(i);
  const dump = {
    trade_date: date,
    snapshot_rows: miDay(i).rows,
    regime_forecast: rg,
    forward_forecast_t1: fcs.map((f) => ({
      sector: f.sector, rank_no: f.rank_no, continuation_prob: f.continuation_prob == null ? null : Number(f.continuation_prob.toFixed(4)),
      exhaustion_risk: Number(f.exhaustion_risk.toFixed(4)), chase_risk: Number(f.chase_risk.toFixed(4)),
      forward_bias: f.forward_bias_t1, sector_tag: f.sector_tag, switch_candidate: f.switch_candidate, evidence: f.evidence
    })),
    verify: run.verify && rg ? miVerify(i, rg, fcs) : '本日期未回填验证',
    intel: intel, next_hot: MI_NEXT_HOT[date] || '本日期未跑', box_source: MI_BOX_LATEST, run_flags: run
  };
  return '<div class="card"><div class="card-title"><h3>接口原始返回（对账用）</h3>' +
      '<span class="hint">正式页面一次请求拿全：快照 + 结构 + 前瞻 + 后验 + 准确率，不用分五个接口拼</span></div>' +
      '<details class="raw" open><summary>regime-view 聚合结果（' + JSON.stringify(dump).length + ' 字节）</summary>' +
      '<pre>' + esc(JSON.stringify(dump, null, 2)) + '</pre></details>' +
      '<details class="raw"><summary>字段口径速查</summary><pre>' + esc([
        'current_regime      mainline / rotation / chaos            结构三态',
        'regime_stage        start / confirm / accelerate / diverge / fade / unknown',
        'regime_confidence   主线 0.7+0.1*min(连续天数,3)；轮动 0.5+0.1*min(换手*10,3)；混沌 0.4；窗口<60 日强制 0.2',
        'forward_bias_t1/t3/t5  continue / switch / fade / diverge / uncertain / mainline_confirm / new_mainline_switch / invalid_rotation',
        'continuation_prob   0.35*近10日在榜率 + 0.20*(1-|量比-1|) + 0.20*min(连续天数/5,1) + 0.15*广度 + 0.10*(1-高位)',
        'exhaustion_risk     0.40*高位 + 0.30*(连续≥5) + 0.20*量能衰减 + 0.10*名次回落',
        'chase_risk          0.50*min(涨幅/10,1) + 0.30*(1-在榜率) + 0.20*高位',
        'sector_tag          mainline_seed / fade_warn / accelerate_warn / low_buy / one_day_fly / none',
        'miss_reason         data_insufficient（窗口未到期）/ uncertain（当时就不判断）/ rule_miss（到期但没命中）',
        'causal_adjustment   当日归因置信度 ≥0.75 → +0.05 延续；<0.45 → -0.05 延续 +0.05 追高；缺失 → 不修正'
      ].join('\n')) + '</pre></details></div>' +
    '<div class="card"><div class="card-title"><h3>判定输入：全板块日快照</h3><span class="hint">改这里的数字，上面所有结论会跟着变</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>名次</th><th>板块</th><th>涨幅</th><th>量比</th><th>上涨家数</th><th>60日箱位</th><th>连续前五</th><th>近10日在榜</th></tr></thead><tbody>' +
      miDay(i).rows.map((r, k) => {
        const f = fcs[k] || null;
        return '<tr><td class="mono">' + r.rank + '</td><td>' + esc(r.sector) + '</td>' +
          '<td>' + (r.chg == null ? '<span class="dim">未保留</span>' : miPctCell(r.chg)) + '</td>' +
          '<td class="mono">' + (r.vol == null ? '—' : r.vol.toFixed(1)) + '</td>' +
          '<td class="mono">' + (r.up == null ? '—' : r.up) + '</td>' +
          '<td class="mono">' + (miBox(r.sector, i) == null ? '<span class="dim">缺失</span>' : Math.round(miBox(r.sector, i) * 100) + '%') + '</td>' +
          '<td class="mono">' + miStreak(r.sector, i) + '</td>' +
          '<td class="mono">' + Math.round(miTop10Freq(r.sector, i) * 100) + '%</td></tr>';
      }).join('') + '</tbody></table></div>' +
      (miDay(i).partial ? '<div class="cap-note warn">' + icon('alert') + '<div>原型只为 ' + esc(date) + ' 之前的日期保留了前五名单（正式库有全部 90 个板块），' +
        '这些日期的涨幅/量比/上涨家数一律显示「未保留」，不补 0 也不补均值。</div></div>' : '') + '</div>';
}

/* ----- 板块抽屉 ----- */
function miSectorDrawerHtml(sector) {
  const i = miI();
  const fcs = miForecasts(i);
  const f = fcs.filter((x) => x.sector === sector)[0] || null;
  const hist = miHist(sector, i);
  const launch = (MI_LAUNCH[miDates()[i]] || []).filter((l) => l.sector === sector)[0] || null;
  const rows = hist.map((h) => '<tr><td class="mono">' + esc(h.date) + '</td><td class="mono">' + h.rank + '</td>' +
    '<td>' + (h.chg == null ? '<span class="dim">未保留</span>' : miPctCell(h.chg)) + '</td>' +
    '<td class="mono">' + (h.vol == null ? '—' : h.vol.toFixed(1)) + '</td>' +
    '<td class="mono">' + (h.up == null ? '—' : h.up + ' 家') + '</td>' +
    '<td class="mono">' + (miBox(sector, miIdx(h.date)) == null ? '—' : Math.round(miBox(sector, miIdx(h.date)) * 100) + '%') + '</td>' +
    '<td>' + (h.rank <= 5 ? tag('前五', 'green') : h.rank <= 10 ? tag('前十', 'mute') : '<span class="dim">出榜</span>') + '</td></tr>').join('');
  const boxSeries = hist.map((h) => (miBox(sector, miIdx(h.date)) == null ? '—' : Math.round(miBox(sector, miIdx(h.date)) * 100) + '%')).join(' → ');
  return '<div class="stack">' +
      '<div class="card"><div class="card-title"><h3>当前判定</h3><span class="hint">' + esc(miDate()) + '</span></div>' +
        (f ? '<div class="mi-drawer-score"><div><span class="metric-label">延续概率</span><div class="metric-value">' +
            (f.continuation_prob == null ? '—' : Math.round(f.continuation_prob * 100) + '%') + '</div></div>' +
          '<div><span class="metric-label">退潮风险</span><div class="metric-value down">' + Math.round(f.exhaustion_risk * 100) + '%</div></div>' +
          '<div><span class="metric-label">追高风险</span><div class="metric-value down">' + Math.round(f.chase_risk * 100) + '%</div></div>' +
          '<div><span class="metric-label">60日箱位</span><div class="metric-value">' + (f.box == null ? '缺失' : Math.round(f.box * 100) + '%') + '</div></div>' +
          '<div><span class="metric-label">连续前五</span><div class="metric-value">' + f.streak + ' 天</div></div></div>' +
          '<div class="mi-bias-acts mi-drawer-bias">' + [['T+1', f.forward_bias_t1], ['T+3', f.forward_bias_t3], ['T+5', f.forward_bias_t5]].map((x) =>
            '<div class="mi-bias-act"><span class="mi-bias-k">' + x[0] + '</span>' + miBias(x[1]) + '</div>').join('') + '</div>' +
          '<dl class="kv mi-kv"><dt>板块标签</dt><dd>' + miSectorTag(f.sector_tag) + '</dd>' +
            '<dt>切换候选</dt><dd>' + (f.switch_candidate ? tag('是：位置不高 + 连续两日在前十 + 量能扩张 + 主线正在退', 'blue') : '否') + '</dd>' +
            '<dt>原因硬度</dt><dd>' + miCausalCell(f) + '</dd>' +
            '<dt>修正影响</dt><dd>' + (f.causal_adjustment == null ? '<span class="dim">未参与修正</span>'
              : '<span class="' + (f.causal_adjustment > 0 ? 'ok-t' : 'bad-t') + '">' + (f.causal_adjustment > 0 ? '+' : '') + (f.causal_adjustment * 100).toFixed(0) +
                ' 延续分</span> <span class="dim">技术面 ' + Math.round((f.evidence.technical_continuation_prob || 0) * 100) + '% → ' + Math.round((f.continuation_prob || 0) * 100) + '%</span>') + '</dd>' +
            '<dt>反证状态</dt><dd>' + (f.falsified ? tag('已触发：延续标签已撤销', 'red') : '未触发') + (f.emotion_only ? ' · ' + tag('情绪票：只做当日', 'gold') : '') + '</dd></dl>'
          : '<div class="empty-list"><strong>这个板块今天不在涨幅前十</strong>没有前瞻分数，只有历史榜位。下面明细仍可核对。</div>') + '</div>' +
      (launch ? miLaunchCard(i, launch, state.miChainMode === 'time' ? 'time' : 'chain', fcs) : '') +
      '<div class="card"><div class="card-title"><h3>近 10 个交易日榜位与量价</h3><span class="hint">行数窗口，不是严格交易日窗口</span></div>' +
        '<div class="table-wrap"><table><thead><tr><th>日期</th><th>名次</th><th>涨幅</th><th>量比</th><th>上涨家数</th><th>60日箱位</th><th>榜位</th></tr></thead>' +
        '<tbody>' + (rows || '<tr><td colspan="7" class="dim">没有历史快照</td></tr>') + '</tbody></table></div>' +
        '<dl class="kv mi-kv"><dt>箱位轨迹</dt><dd class="mono">' + esc(boxSeries) + '</dd></dl></div>' +
      '<div class="card"><div class="card-title"><h3>这个板块的下游入口</h3></div>' +
        '<div class="row mi-actions">' +
          '<button class="btn sm" data-nav="#/candidates">' + icon('search', 'sm') + '在候选池按板块筛个股</button>' +
          '<button class="btn sm" data-nav="#/holdings">' + icon('home', 'sm') + '看持仓里有没有它</button>' +
        '</div>' +
        '<div class="cap-note">' + icon('info') + '<div>正式页面会把板块名作为筛选条件带到候选池与持仓页。这里不列个股，个股结论只在候选池与持仓页出现。</div></div></div>' +
    '</div>';
}

/* ----- 交互 ----- */
function miPushLog(text, step) { miLog(miI(), step || 'op', text); }
function miRequireSnap(i) {
  if (miDay(i).partial) {
    toast('这一天的快照只剩前五名单', '正式库里每个交易日都有 90 个板块。原型只为最近 14 个交易日保留了完整十行，补跑出来的结论只能演示，别当历史回填。', 'warn');
  }
  return true;
}
function handleMarketIntelAction(action, el) {
  const i = miI();
  if (action === 'mi-board') { state.miBoard = el.dataset.b; renderView(); syncMarketIntelHash(); return; }
  if (action === 'mi-date') { state.miDate = el.dataset.date; state.miSector = null; closeDrawer(); renderView(); syncMarketIntelHash(); return; }
  if (action === 'mi-step') {
    const n = Math.max(0, Math.min(miDates().length - 1, i + Number(el.dataset.d)));
    state.miDate = miDates()[n];
    renderView(); syncMarketIntelHash(); return;
  }
  if (action === 'mi-horizon') { state.miHorizon = el.dataset.h; renderView(); syncMarketIntelHash(); return; }
  if (action === 'mi-refresh') { renderView(); syncMarketIntelHash(); toast('已按页面数据重算', '结构、前瞻、后验都是现算的，没有调后端。', 'info'); return; }
  if (action === 'mi-clear-log') { state.miLog = []; renderView(); return; }
  if (action === 'mi-chain-mode') { state.miChainMode = el.dataset.m; renderView(); return; }
  if (action === 'mi-expand') {
    const k = el.dataset.k;
    state.miExpand[k] = !state.miExpand[k];
    renderView();
    return;
  }
  if (action === 'mi-sector') {
    const s = el.dataset.s;
    state.miSector = s;
    openDrawer('mi-sector', s);
    syncMarketIntelHash();
    return;
  }
  if (action === 'mi-run-regime') {
    miRequireSnap(i);
    const r = miRun(i);
    if (r.regime) { toast('这天已经有结构判定', '要看回填后的准确率，用「回填验证」。', 'info'); return; }
    r.regime = true; r.forward = true;
    miPushLog('补跑行情结构 + 板块前瞻：' + MI_REGIME_LABEL[miRegime(i).current_regime] + ' · ' + MI_STAGE_LABEL[miRegime(i).regime_stage], 'regime');
    renderView(); syncMarketIntelHash();
    const rg = miRegime(i);
    toast('结构判定完成', miDates()[i] + '：' + MI_REGIME_LABEL[rg.current_regime] + ' · 阶段「' + MI_STAGE_LABEL[rg.regime_stage] + '」，' +
      '前十板块三窗口前瞻已写入。正式系统需要后端补一个手动跑结构的接口，现在的按钮只能跑板块前瞻。', 'ok');
    return;
  }
  if (action === 'mi-run-verify') {
    let n = 0;
    miDates().forEach((d, k) => { if (miRun(k).regime) { miRun(k).verify = true; n += 1; } });
    miPushLog('回填验证：已把 ' + n + ' 个判定日的后验窗口重新算了一遍', 'verify');
    renderView(); syncMarketIntelHash();
    toast('后验已回填', '未到期窗口仍然显示「还差 N 天」，不计入命中率也不伪造。', 'ok');
    return;
  }
  if (action === 'mi-run-intel') {
    const r = miRun(i);
    if (r.intel) { toast('这天的 AI 研判已存在', '原型里的研判文字是固定的，重新生成不会给出不同措辞。', 'info'); return; }
    if (!r.regime) { toast('先跑行情结构', 'AI 研判要读结构判定和板块前瞻的结果，这一天两者都没有。', 'warn'); return; }
    if (state.miIntelBusy) return;
    state.miIntelBusy = miDates()[i];
    renderView();
    miPushLog('提交 AI 研判后台任务（16:20 那段）', 'intel');
    setTimeout(() => {
      state.miIntelBusy = null;
      miRun(miIdx(miDates()[i])).intel = true;
      miPushLog('AI 研判完成（本页用模板按同一批数字拼出文字，正式系统由大模型撰写）', 'intel');
      renderView(); syncMarketIntelHash();
      toast('研判完成', miDates()[i] + ' 的判定依据、核心矛盾、操作含义、次日盯盘点已补上，并标注为模板生成。', 'ok');
    }, 900);
    return;
  }
  if (action === 'mi-run-rotation') {
    const r = miRun(i);
    if (r.rotation) { toast('轮动归因已回填', 'AI 版归因每条约 5 分钟，正式系统里它跑在独立批里，可能晚于 16:20 研判。', 'info'); return; }
    r.rotation = true;
    miPushLog('生成轮动归因（AI 版）', 'rotation');
    renderView(); syncMarketIntelHash();
    toast('轮动归因完成', '板块启动理由与 AI 评估已补上；文字只作解释，不进前瞻分数。', 'ok');
    return;
  }
}
function syncMarketIntelHash() {
  if (state.route !== '#/market-intel') return;
  let next = '#/market-intel?date=' + miDate() + '&board=' + state.miBoard + '&h=' + state.miHorizon;
  if (state.miSector) next += '&sector=' + encodeURIComponent(state.miSector);
  if (location.hash !== next) history.replaceState(null, '', next);
}


/* ---------- 建仓计划：事实种子 + 量化引擎（逐条复刻 backend/app/services/plan_quant.py） ---------- */
const PL_TODAY = '2026-11-16';               // 原型模拟日，与持仓页/候选池同一天
const PL_BASE_CAPITAL = 460000;          // settings.total_capital：.env 基准总资产（与持仓页实时总资产不同源）
const PL_GRADE_CAP = { A: 0.30, B: 0.20, C: 0.10 };  // core.config GRADE_POSITION_CAP
const PL_CAP_FALLBACK = 0.20;            // plan_quant.py:86 GRADE_CAP_PCT.get(grade, 0.20)
const PL_C2_TOTAL = 0.60;                // C2_TOTAL_POSITION_CAP
const PL_C3_FACTOR = 0.92;               // C3_STOP_FACTOR
const PL_BREAKEVEN_MIN = 3.0;
const PL_REDUCE_FACTOR = 0.7;
const PL_LOT = 100;
const PL_SCORE_MAX_DAYS = 3;             // settings.score_freshness_max_trading_days（S-7）
const PL_CACHE_TTL = 1800;               // router.py:124 B 级 30 分钟缓存
const PL_C1_CONCENTRATION = 60;          // C1_CONCENTRATION_CAP：单只占总资产集中度告警线（与分级上限同名不同义）

/* 计划生成当时的持仓市值：今天这条直接用持仓页实时市值，保证两个页面对得上 */
const PL_MV_AT = { '2026-11-16': 402300, '2026-11-13': 232400, '2026-11-12': 96000, '2026-11-10': 118000 };
/* 计划生成当时读到的最新收盘价（position.py indicators.latest_close） */
const PL_CLOSE_AT = {
  '2026-11-16': { '603501': [126.30, '2026-11-16'], '600893': [43.20, '2026-11-16'] },
  '2026-11-13': { '603501': [121.80, '2026-11-13'], '002371': [322.40, '2026-11-12'], '300750': [262.10, '2026-11-13'] },
  '2026-11-12': { '002049': [79.40, '2026-11-12'], '601012': [26.80, '2026-11-12'], '600519': [1386.00, '2026-11-12'] },
  '2026-11-10': { '002415': [30.80, '2026-11-10'], '300399': [118.60, '2026-11-10'] }
};
/* 今天的行情快照：用来对照「计划里冻结的价格」和「现在真实价格」差了多少 */
const PL_LIVE_NOW = {
  '603501': 126.30, '600893': 43.20, '002049': 88.00, '002371': 318.60, '300750': 268.40,
  '601012': 27.10, '600519': 1392.00, '002415': 31.26, '300399': 105.80, '688981': 88.20, '000725': 4.32
};
/* 综合评级与评分日（StockScore）；age=距今天数超过 PL_SCORE_MAX_DAYS 一律降级「未评级」 */
const PL_SCORES = {
  '603501': { grade: 'A', score: 88, score_date: '2026-11-16', age: 0, risk: ['板块拥挤度偏高，短线追高', '跌破 100 元整数位需止损'] },
  '002049': { grade: 'A', score: 84, score_date: '2026-11-12', age: 2, risk: ['机构分歧加大，量能未持续放大'] },
  '600893': { grade: 'B', score: 81, score_date: '2026-11-09', age: 5, risk: ['订单确认周期长', '评分已过期，需重跑'] },
  '002371': { grade: 'B', score: 79, score_date: '2026-11-13', age: 3, risk: ['单价高，一手金额大', '设备招标节奏不稳'] },
  '601012': { grade: 'B', score: 76, score_date: '2026-11-12', age: 4, risk: ['产业链价格仍在下探'] },
  '300399': { grade: 'B', score: 77, score_date: '2026-11-10', age: 6, risk: ['客户集中度高'] },
  '002415': { grade: 'B', score: 78, score_date: '2026-11-10', age: 6, risk: ['海外收入占比高，汇率敏感'] },
  '300750': { grade: 'B', score: 80, score_date: '2026-11-13', age: 3, risk: ['排产下修传闻待确认'] },
  '600519': { grade: 'A', score: 86, score_date: '2026-11-12', age: 4, risk: ['单价 1392 元，一手金额超单票上限'] },
  '688981': { grade: 'C', score: 74, score_date: '2026-11-16', age: 0, risk: ['评级不足，禁止生成建仓计划'] },
  '000725': { grade: 'C', score: 71, score_date: '2026-11-16', age: 0, risk: ['评级不足'] }
};

/* LLM 只负责区间/配比/止损止盈/市场强弱（position.py llm_plan），数值全部由量化层重算 */
const PLANS = [
  {
    id: 4110, stock_code: '603501', stock_name: '韦尔股份', plan_date: '2026-11-16',
    status: 'proposed', source: 'candidate', supersedes_id: 4101, created_at: '2026-11-16 09:12:40',
    total_pct: 30, stop_loss: 116.5, take_profit: 148.0,
    batches: [
      { tranche: '第一档', price_zone: '121 - 124', ratio_pct: 50, trigger_note: '回踩 5 日线且量比不低于 0.8 时首仓' },
      { tranche: '第二档', price_zone: '125 - 128', ratio_pct: 30, trigger_note: '放量突破 126 元并站稳半日' },
      { tranche: '第三档', price_zone: '129 - 132', ratio_pct: 20, trigger_note: '板块同步走强，不追单只独涨' }
    ],
    rationale: '主线板块放量延续，评分 88 达 A 级；按三档推进，首档不超过单票上限一半。',
    market_regime: '半导体为当前主线龙头，榜面连续居前且量能扩张，结构处于确认段。',
    dimensions: [
      { dim: '趋势', score: 82, verdict: '支持', advice: '站稳 126 后打开上行空间，回踩不破 121 可加。' },
      { dim: '资金', score: 76, verdict: '支持', advice: '主力净流入连续 3 日，但单日额已缩。' },
      { dim: '题材', score: 88, verdict: '支持', advice: '订单能见度提升属产业逻辑，非纯情绪。' },
      { dim: '风险', score: 44, verdict: '风险', advice: '板块拥挤度偏高，追高需等回踩。' }
    ],
    final_advice: '可建仓，但只在回踩档介入；当前账户仓位已超 C2 上限，实际可用资金为 0，本计划金额会被压到 0。'
  },
  {
    id: 4111, stock_code: '600893', stock_name: '航发动力', plan_date: '2026-11-16',
    status: 'proposed', source: 'candidate', supersedes_id: null, created_at: '2026-11-16 09:12:55',
    total_pct: 20, stop_loss: 40.2, take_profit: 47.5,
    batches: [
      { tranche: '第一档', price_zone: '41.5 - 42.2', ratio_pct: 60, trigger_note: '缩量回踩 10 日线' },
      { tranche: '第二档', price_zone: '42.6 - 43.4', ratio_pct: 40, trigger_note: '军工板块整体放量当日跟入' }
    ],
    rationale: '景气延续但评分已过期，本轮由候选池联动重跑生成。',
    market_regime: '军工非本轮主线，榜面换手偏高，按轮动行情处理。',
    dimensions: [
      { dim: '趋势', score: 66, verdict: '支持', advice: '沿 10 日线震荡上行。' },
      { dim: '资金', score: 52, verdict: '中性', advice: '资金流入不连续。' },
      { dim: '风险', score: 38, verdict: '风险', advice: '评分日 2026-11-09 已超 3 个交易日，按未评级处理。' }
    ],
    final_advice: '评分过期标的：门槛会拒绝生成，这条是过期前最后一次生成的留存。'
  },
  {
    id: 4101, stock_code: '603501', stock_name: '韦尔股份', plan_date: '2026-11-13',
    status: 'accepted', source: 'candidate', supersedes_id: 4100, created_at: '2026-11-13 09:14:02',
    total_pct: 30, stop_loss: 112.0, take_profit: 142.0,
    batches: [
      { tranche: '第一档', price_zone: '118 - 120', ratio_pct: 40, trigger_note: '开盘不破 118 直接介入' },
      { tranche: '第二档', price_zone: '121 - 124', ratio_pct: 35, trigger_note: '放量站上 121' },
      { tranche: '第三档', price_zone: '125 - 127', ratio_pct: 25, trigger_note: '主线未分歧时补齐' }
    ],
    rationale: '主线确认段，三档介入，首档不超过单票上限一半。',
    market_regime: '半导体连续 4 日居榜首，结构主线·确认。',
    dimensions: [
      { dim: '趋势', score: 80, verdict: '支持', advice: '突破 117 后回踩确认。' },
      { dim: '资金', score: 74, verdict: '支持', advice: '主力净流入 5 日 4 天为正。' },
      { dim: '题材', score: 86, verdict: '支持', advice: '订单与出货指引双上修。' },
      { dim: '风险', score: 40, verdict: '风险', advice: '拥挤度偏高，不追高开。' }
    ],
    final_advice: '采纳后按档执行；系统不下单，成交结果需你在持仓页人工登记。'
  },
  {
    id: 4100, stock_code: '603501', stock_name: '韦尔股份', plan_date: '2026-11-13',
    status: 'superseded', source: 'candidate', supersedes_id: null, created_at: '2026-11-13 08:58:10',
    total_pct: 20, stop_loss: 110.0, take_profit: 132.0,
    batches: [
      { tranche: '第一档', price_zone: '116 - 119', ratio_pct: 55, trigger_note: '回踩 10 日线' },
      { tranche: '第二档', price_zone: '120 - 123', ratio_pct: 45, trigger_note: '站上 120 补齐' }
    ],
    rationale: '同标的当日重算，旧版本被 4101 替代。',
    market_regime: '半导体主线，量能未完全确认。',
    dimensions: [
      { dim: '趋势', score: 74, verdict: '支持', advice: '震荡上行但未突破前高。' },
      { dim: '资金', score: 62, verdict: '中性', advice: '流入强度一般。' }
    ],
    final_advice: '已被同标的同交易日的更新版本替代。'
  },
  {
    id: 4102, stock_code: '002371', stock_name: '北方华创', plan_date: '2026-11-13',
    status: 'proposed', source: 'manual', supersedes_id: null, created_at: '2026-11-13 10:22:31',
    total_pct: 20, stop_loss: 296.0, take_profit: 372.0,
    batches: [
      { tranche: '第一档', price_zone: '305 - 315', ratio_pct: 60, trigger_note: '回踩 20 日线不破' },
      { tranche: '第二档', price_zone: '320 - 330', ratio_pct: 40, trigger_note: '板块放量跟随' }
    ],
    rationale: '设备招标放量，手动生成；单价高，受可用资金与一手门槛双重约束。',
    market_regime: '半导体设备为主线分支，榜面连续居前。',
    dimensions: [
      { dim: '趋势', score: 78, verdict: '支持', advice: '沿 20 日线上行。' },
      { dim: '资金', score: 70, verdict: '支持', advice: '主力小幅净流入。' },
      { dim: '风险', score: 55, verdict: '风险', advice: '单价 322 元，一手需 3.2 万元。' }
    ],
    final_advice: '金额被 C2 可用资金压缩后，第一档买不满一手，实际无法按档执行。'
  },
  {
    id: 4103, stock_code: '300750', stock_name: '宁德时代', plan_date: '2026-11-13',
    status: 'abandoned', source: 'candidate', supersedes_id: null, created_at: '2026-11-13 09:15:02',
    total_pct: 20, stop_loss: 245.0, take_profit: 300.0,
    batches: [
      { tranche: '第一档', price_zone: '252 - 258', ratio_pct: 50, trigger_note: '排产数据确认前' },
      { tranche: '第二档', price_zone: '260 - 266', ratio_pct: 50, trigger_note: '确认后补齐' }
    ],
    rationale: '旧版本记录：量化字段缺失（v3.0 之前生成），只有 LLM 比例明细。',
    market_regime: '（旧数据未落市场强弱）',
    dimensions: [],
    final_advice: '',
    legacy: true
  },
  {
    id: 4090, stock_code: '002049', stock_name: '紫光国微', plan_date: '2026-11-12',
    status: 'proposed', source: 'candidate', supersedes_id: null, created_at: '2026-11-12 09:13:20',
    total_pct: 30, stop_loss: 74.0, take_profit: 85.5,
    batches: [
      { tranche: '第一档', price_zone: '76 - 78', ratio_pct: 45, trigger_note: '回踩 5 日线' },
      { tranche: '第二档', price_zone: '79 - 81', ratio_pct: 35, trigger_note: '放量站上 80' },
      { tranche: '第三档', price_zone: '82 - 84', ratio_pct: 20, trigger_note: '主线延续再加' }
    ],
    rationale: '国产替代逻辑延续，机构评级上调；但止盈目标偏近，盈亏比不足 3:1。',
    market_regime: '半导体主线确认段。',
    dimensions: [
      { dim: '趋势', score: 82, verdict: '支持', advice: '突破 79 后打开空间。' },
      { dim: '资金', score: 72, verdict: '支持', advice: '融资余额回升。' },
      { dim: '题材', score: 80, verdict: '支持', advice: '评级上调驱动。' },
      { dim: '风险', score: 48, verdict: '风险', advice: '盈亏比不足，止盈距离太近。' }
    ],
    final_advice: '盈亏比不达标，仓位已按规则自动降档；若不能接受更紧的止损纪律，建议放弃本方案。'
  },
  {
    id: 4091, stock_code: '601012', stock_name: '隆基绿能', plan_date: '2026-11-12',
    status: 'proposed', source: 'candidate', supersedes_id: null, created_at: '2026-11-12 09:13:41',
    total_pct: 20, stop_loss: 24.6, take_profit: 33.0,
    batches: [
      { tranche: '第一档', price_zone: '25.6 - 26.4', ratio_pct: 55, trigger_note: '缩量回踩 20 日线' },
      { tranche: '第二档', price_zone: '26.8 - 27.6', ratio_pct: 45, trigger_note: '产业链价格企稳后' }
    ],
    rationale: '超跌 + 产业链价格止跌预期，分两档左侧介入。',
    market_regime: '光伏不在本轮主线，榜面留存率低，按轮动处理。',
    dimensions: [
      { dim: '趋势', score: 58, verdict: '中性', advice: '仍在 60 日线下方。' },
      { dim: '资金', score: 66, verdict: '支持', advice: '北向回流。' },
      { dim: '风险', score: 50, verdict: '风险', advice: '产业链价格尚未确认止跌。' }
    ],
    final_advice: '可小仓试错，盈亏比达标但结构不站在这一边，仓位按 B 级上限执行。'
  },
  {
    id: 4092, stock_code: '600519', stock_name: '贵州茅台', plan_date: '2026-11-12',
    status: 'proposed', source: 'manual', supersedes_id: null, created_at: '2026-11-12 15:40:02',
    total_pct: 30, stop_loss: 1310.0, take_profit: 1560.0,
    batches: [
      { tranche: '第一档', price_zone: '1360 - 1380', ratio_pct: 60, trigger_note: '跌破 1360 不介入' },
      { tranche: '第二档', price_zone: '1390 - 1410', ratio_pct: 40, trigger_note: '站稳 1400 补齐' }
    ],
    rationale: '手动生成用于对照高单价标的：单票上限金额买不满一手。',
    market_regime: '消费白马非主线，资金避险属性。',
    dimensions: [
      { dim: '趋势', score: 62, verdict: '中性', advice: '横盘震荡。' },
      { dim: '风险', score: 42, verdict: '风险', advice: '一手 13.92 万元，超单票上限可用金额。' }
    ],
    final_advice: '量化结果会给出 0 股：金额上限买不起一手，方案不可执行。',
    noAsOf: true
  },
  {
    id: 4080, stock_code: '002415', stock_name: '海康威视', plan_date: '2026-11-10',
    status: 'accepted', source: 'candidate', supersedes_id: null, created_at: '2026-11-10 09:12:18',
    total_pct: 20, stop_loss: 28.9, take_profit: 35.5,
    batches: [
      { tranche: '第一档', price_zone: '29.8 - 30.6', ratio_pct: 55, trigger_note: '回踩 20 日线' },
      { tranche: '第二档', price_zone: '30.8 - 31.6', ratio_pct: 45, trigger_note: '放量站上 31' }
    ],
    rationale: 'AI 视觉 + 海外恢复，B 级上限内两档建仓。',
    market_regime: '安防分支跟随主线，榜面留存中等。',
    dimensions: [
      { dim: '趋势', score: 72, verdict: '支持', advice: '站上 30 元平台。' },
      { dim: '资金', score: 68, verdict: '支持', advice: '主力温和流入。' },
      { dim: '风险', score: 52, verdict: '风险', advice: '汇率敏感。' }
    ],
    final_advice: '已采纳：成交结果请在持仓页人工登记，系统不会自动转持仓。'
  },
  {
    id: 4081, stock_code: '300399', stock_name: '天孚通信', plan_date: '2026-11-10',
    status: 'superseded', source: 'manual', supersedes_id: null, created_at: '2026-11-10 14:05:12',
    total_pct: 20, stop_loss: 112.0, take_profit: 138.0,
    batches: [
      { tranche: '第一档', price_zone: '115 - 118', ratio_pct: 50, trigger_note: '光模块板块共振' },
      { tranche: '第二档', price_zone: '119 - 123', ratio_pct: 50, trigger_note: '放量突破 123' }
    ],
    rationale: '手动生成，后续被候选池版本替代。',
    market_regime: '光模块为主线分支，但当日榜面换手抬升。',
    dimensions: [
      { dim: '趋势', score: 76, verdict: '支持', advice: '沿 5 日线上行。' },
      { dim: '风险', score: 46, verdict: '风险', advice: '客户集中，单日波动大。' }
    ],
    final_advice: '已被新版本替代；止损位 112 已在今日盘中击穿。'
  }
];

const PL_STATUS_LABEL = {
  proposed: '待确认', accepted: '已采纳', abandoned: '已放弃',
  superseded: '已被新版本替代', expired: '已过期'
};
const PL_STATUS_TONE = { proposed: 'warn', accepted: 'green', abandoned: 'mute', superseded: 'mute', expired: 'gold' };
const PL_SOURCE_LABEL = { candidate: '每日候选池', manual: '手动生成' };
/* 后端 position.py:200-206 只会产出三种；realtime / cache30m 在映射表里但从不被写入 */
const PL_FRESHNESS_LABEL = {
  realtime: ['实时数据', 'green', '后端不会输出这个值'],
  cache30m: ['30分钟缓存', 'warn', '后端不会输出这个值'],
  same_day_as_of: ['当日数据截至', 'blue', ''],
  prior_close: ['前收数据', 'mute', ''],
  unknown: ['数据时效未知', 'red', '']
};

function plRound2(v) { return v == null ? null : Math.round(Number(v) * 100) / 100; }
function plLots(amount, price) {
  if (!amount || !price || price <= 0) return 0;
  return Math.floor(amount / price / PL_LOT) * PL_LOT;
}
function plZoneMid(zone) {
  const nums = String(zone == null ? '' : zone).match(/\d+\.?\d*/g) || [];
  if (nums.length >= 2) return (parseFloat(nums[0]) + parseFloat(nums[1])) / 2;
  if (nums.length === 1) return parseFloat(nums[0]);
  return null;
}
function plMv(dateKey) {
  if (dateKey === PL_TODAY) return hdTotalMv();
  return PL_MV_AT[dateKey] == null ? hdTotalMv() : PL_MV_AT[dateKey];
}
function plScore(code) { return PL_SCORES[code] || null; }
function plGradeOf(code) {
  const s = plScore(code);
  if (!s) return '无评级';
  if (s.age > PL_SCORE_MAX_DAYS) return '未评级';   // S-7：过期评分降级
  return s.grade;
}
function plGradeUsable(code) {
  const g = plGradeOf(code);
  return g === 'A' || g === 'B';
}
/* 复刻 plan_quant.quantify：输入 LLM 明细 + 评级 + 当时收盘价，输出全部数值字段 */
function plQuant(p) {
  if (p.legacy) return null;
  const s = plScore(p.stock_code) || {};
  const grade = plGradeOf(p.stock_code) === '未评级' ? '未评级' : (s.grade || '');
  const capPct = PL_GRADE_CAP[grade] == null ? PL_CAP_FALLBACK : PL_GRADE_CAP[grade];
  const mv = plMv(p.plan_date);
  const available = Math.max(0, PL_BASE_CAPITAL * PL_C2_TOTAL - mv);
  let positionAmount = PL_BASE_CAPITAL * capPct;
  const notes = [];
  if (positionAmount > available) {
    positionAmount = available;
    notes.push('账户可用资金不足（C2 总仓约束），计划金额已自动缩减');
  }
  const closePair = (PL_CLOSE_AT[p.plan_date] || {})[p.stock_code] || [null, null];
  const price = Number(closePair[0] || 0);
  let costRef = price;
  if (p.batches && p.batches.length) {
    const mid = plZoneMid((p.batches[0] || {}).price_zone);
    if (mid) costRef = mid;
  }
  const c3Stop = costRef > 0 ? plRound2(costRef * PL_C3_FACTOR) : null;
  const llmStop = Number(p.stop_loss || 0);
  let initialStop = Math.max(c3Stop || 0, llmStop) || 0;
  initialStop = plRound2(initialStop) || c3Stop;
  const tp = plRound2(Number(p.take_profit || 0));
  let breakeven = null;
  if (tp && costRef > 0 && initialStop && costRef > initialStop) {
    breakeven = Math.round((tp - costRef) / (costRef - initialStop) * 100) / 100;
  }
  let reduced = false;
  if (breakeven != null && breakeven < PL_BREAKEVEN_MIN) {
    positionAmount = Math.round(positionAmount * PL_REDUCE_FACTOR * 100) / 100;
    reduced = true;
    notes.push('盈亏比 ' + breakeven + ':1 不足 3:1，仓位已自动降低至 ' + (PL_REDUCE_FACTOR * 100) + '% 并请重点跟踪止损纪律');
  }
  const totalRatio = p.batches.reduce((a, b) => a + Number(b.ratio_pct || 0), 0) || 1;
  let cum = 0;
  const batches = p.batches.map((b) => {
    const ratio = Number(b.ratio_pct || 0) / totalRatio;
    const amt = plRound2(positionAmount * ratio);
    const mid = plZoneMid(b.price_zone) || price;
    cum = Math.round((cum + ratio * 100) * 10) / 10;
    return {
      tranche: b.tranche, price_zone: String(b.price_zone || ''), trigger_note: String(b.trigger_note || ''),
      amount: amt, shares: plLots(amt, mid), cum_pct: cum, unit: mid
    };
  });
  const totalShares = batches.reduce((a, b) => a + b.shares, 0);
  const totalAmount = plRound2(batches.reduce((a, b) => a + (b.amount || 0), 0));
  const expectedTotalPct = PL_BASE_CAPITAL > 0 ? plRound2((mv + (totalAmount || 0)) / PL_BASE_CAPITAL * 100) : null;
  const dataAsOf = p.noAsOf ? '' : (closePair[1] || '');
  return {
    current_price: plRound2(price), price_date: dataAsOf || p.plan_date,
    total_capital: plRound2(PL_BASE_CAPITAL), account_mv: plRound2(mv),
    available_capital: plRound2(available),
    position_cap_pct: capPct * 100, position_amount: plRound2(positionAmount),
    position_shares: plLots(positionAmount, price),
    cost_basis: plRound2(costRef), initial_stop: initialStop, c3_stop: c3Stop, take_profit: tp,
    breakeven_ratio: breakeven, breakeven_ok: breakeven != null && breakeven >= PL_BREAKEVEN_MIN,
    expected_total_pct: expectedTotalPct, reduced: reduced, notes: notes,
    batches: batches, total_shares: totalShares, total_amount: totalAmount,
    grade: grade, cap_pct: capPct,
    rounding_gap: plRound2(positionAmount - (totalAmount || 0)),
    lot_short: batches.filter((b) => b.amount > 0 && b.shares === 0).length,
    freshness: !dataAsOf ? 'unknown' : (dataAsOf === p.plan_date ? 'same_day_as_of' : 'prior_close'),
    data_as_of: dataAsOf || null
  };
}
function plQ(p) { return p._q || (p._q = plQuant(p)); }
/* 信号态：生产用计划里冻结的价格判断，不是今天的实时价 */
function plSignal(p) {
  const q = plQ(p);
  if (!q) return { label: '无量化字段', tone: 'mute', bar: 'var(--mute)' };
  const cur = Number(q.current_price), tp = parseFloat(q.take_profit), sl = parseFloat(q.initial_stop);
  if (Number.isFinite(cur) && Number.isFinite(tp) && cur >= tp) return { label: '止盈已触发', tone: 'up', bar: 'var(--up)' };
  if (Number.isFinite(cur) && Number.isFinite(sl) && cur <= sl) return { label: '止损已触发', tone: 'down', bar: 'var(--down)' };
  return { label: '监控中', tone: 'warn', bar: 'var(--warn)' };
}
function plLiveDrift(p) {
  const q = plQ(p);
  const live = PL_LIVE_NOW[p.stock_code];
  if (!q || !q.current_price || live == null) return null;
  const pct = Math.round((live - q.current_price) / q.current_price * 10000) / 100;
  const sl = Number(q.initial_stop), tp = Number(q.take_profit);
  let should = null;
  if (Number.isFinite(tp) && live >= tp) should = '止盈已触发';
  else if (Number.isFinite(sl) && live <= sl) should = '止损已触发';
  return { live: live, pct: pct, price_date: q.price_date, should: should };
}
function plChain(p) {
  return PLANS.filter((x) => x.stock_code === p.stock_code && x.plan_date === p.plan_date)
    .sort((a, b) => b.id - a.id);
}
function plDates() {
  return Array.from(new Set(PLANS.map((p) => p.plan_date))).sort((a, b) => (a < b ? 1 : -1));
}
const PL_SOURCE_OPTS = [['全部来源', ''], ['每日候选池', 'candidate'], ['手动生成', 'manual']];
function plFilters() {
  /* 首次进入默认只看最近一个交易日（与正式页面一致）；显式选「全部日期」后才放开 */
  const dates = plDates();
  if (!state.plDate) state.plDate = dates[0] || '全部日期';
  return {
    status: state.plStatus || '全部', date: state.plDate,
    grade: state.plGrade || '全部评级', source: state.plSource || '全部来源',
    code: state.plCode || ''
  };
}
function plRows() {
  const f = plFilters();
  let rows = PLANS.slice();
  if (f.status !== '全部') rows = rows.filter((p) => PL_STATUS_LABEL[p.status] === f.status);
  if (f.date !== '全部日期') rows = rows.filter((p) => p.plan_date === f.date);
  if (f.grade !== '全部评级') {
    rows = rows.filter((p) => {
      const g = plGradeOf(p.stock_code);
      return f.grade === '未评级' ? (g !== 'A' && g !== 'B') : g === f.grade;
    });
  }
  if (f.code) rows = rows.filter((p) => p.stock_code === f.code);
  if (f.source !== '全部来源') {
    const key = (PL_SOURCE_OPTS.filter((o) => o[0] === f.source)[0] || ['', ''])[1];
    rows = rows.filter((p) => (p.source || 'manual') === key);
  }
  return rows.sort((a, b) => (a.id < b.id ? 1 : -1));
}
function plConclusion(p) {
  const d = String(p.final_advice || p.rationale || '').trim();
  return d || '暂无结论';
}
function plMoney(v) { return v == null ? '—' : Number(v).toLocaleString('zh-CN'); }
function plPct(v, digits) { return v == null ? '—' : Number(v).toFixed(digits == null ? 1 : digits) + '%'; }

/* 结构判定那一步的已知毛病，同样对着后端代码核过 */
const PL_GAPS = [
  ['满仓时仍会落一份 0 元计划', '可用资金 = 总资产基准×60% − 当前持仓市值，账户已经超了 C2 上限时这一项归零，量化层把计划金额压成 0、股数压成 0，然后照样落库、照样返回成功。页面看到的是「待确认」，实际一份都买不了。落地要把这种情况单独标成「不可执行」，并说明是先减仓还是改基准。'],
  ['计划里的总资产与持仓页不是一个数', '量化层用配置项基准总资产算上限和可用资金，持仓页显示的是实时总资产（基准 + 浮动盈亏）。本原型基准 460,000、持仓页 486,200，A 级单票上限按前者算是 138,000，按后者算是 145,860，差 7,860。两个页面各说一个数，用户会以为算错了。'],
  ['「C1」在页面上指两个不同的东西', '分档明细的合计行写「不突破 C1 单票上限」，取的是分级上限（A 30% / B 20% / C 10%）；风控规则行也写「单票 ≤ C1」，但配置里 C1 是单只占总资产 60% 的集中度告警线。同名两义，正式页面原样输出。本页把两个名字分开写。'],
  ['止盈止损信号用的是冻结价格', '「监控中 / 止盈已触发 / 止损已触发」拿的是计划生成当时读到的收盘价，不是今天的行情，标签落库后永远不变。天孚通信止损位 112、今天 105.8 已跌破，紫光国微止盈位 85.5、今天 88 已到位，两条都还显示「监控中」。列表里 11 条计划没有一条不是「监控中」。要么接实时价重算，要么把标签改成「按生成时价格判断」，不能挂着「已触发」的措辞骗人。'],
  ['盈亏比降档的说明前端根本没显示', '量化层把「盈亏比不足 3:1，仓位已自动降低至 70%」写进 notes，还有 reduced / breakeven_ok / available_capital / c3_stop / price_date 这些字段，正式建仓计划页一个都没渲染。用户只看到仓位变小了，不知道为什么。'],
  ['B 级 30 分钟缓存命中不留痕', 'B 级标的当日已有计划且未满 30 分钟时直接复用旧计划、不调模型，但返回里只带一个 cached 标记，计划记录本身没有任何变化，时效字段仍是「当日数据截至」。用户点「重算」以为算了新的，其实拿到的是半小时前那份。'],
  ['已放弃、已替代的方案还能被改成已采纳', '状态更新接口只校验值域是不是 accepted/abandoned，不校验当前状态，也不校验同一标的是否已有生效版本。于是同一标的同一交易日可以同时存在「已采纳」和「待确认」两份，本原型 11-16 与 11-13 的韦尔股份就是这个状态。'],
  ['未评级的默认档与注释承诺不一致', '注释说评分过期降级后走 C 级默认档（10%），代码取的是 .get(评级, 0.20)，也就是 20%——等于 B 级。现在因为门槛直接拒绝未评级生成，这一档碰不到；一旦门槛放宽，未评级会按 B 级放量。'],
  ['时效映射表里有两个值永远不会出现', '正式页面的时效表列了「实时数据 / 30分钟缓存 / 当日数据截至 / 前收数据 / 数据时效未知」五种，后端只会输出后三种（日线不宣称盘中实时）。前两种留着会误导排查。'],
  ['「过期」状态没有任何写入方', '模型注释里状态有 proposed/accepted/expired/superseded，代码里 expired 从没被写过，也没有定时任务把过期未处理的方案收掉。待确认方案会一直挂着。'],
  ['手动重算永远只能算今天', '后台任务处理器调用生成链路时不传交易日期，历史日期的方案无法重算。要补某一天只能在定时任务里跑。'],
  ['高单价标的会算出 0 股', '金额上限买不起一手时，股数向下取整到 100 的整数倍就归零，量化层不报错也不提示。贵州茅台那条计划上限 138,000 元、一手 139,200 元，结果每一档都是 0 股。']
];

/* ---------- 建仓计划页 ---------- */
const PL_STATUS_ORDER = ['proposed', 'accepted', 'abandoned', 'superseded', 'expired'];
const PL_STATUS_CLS = { proposed: 'gold', accepted: 'green', abandoned: 'mute', superseded: 'mute', expired: 'outline' };
const PL_FRESH_CLS = { realtime: 'green', cache30m: 'gold', same_day_as_of: 'blue', prior_close: 'mute', unknown: 'red' };
const PL_GRADE_CLS = { A: 'red', B: 'gold', C: 'blue', 未评级: 'mute', 无评级: 'mute' };

function plStatusTag(st) { return tag(PL_STATUS_LABEL[st] || st, PL_STATUS_CLS[st] || 'mute'); }
function plFreshTag(f) {
  const m = PL_FRESHNESS_LABEL[f] || [f, 'mute', ''];
  return '<span title="' + esc(m[2]) + '">' + tag(m[0], m[1]) + '</span>';
}
function plGradeTag(code) {
  const g = plGradeOf(code), s = plScore(code);
  return tag(g + (s && s.score ? ' ' + s.score : ''), PL_GRADE_CLS[g] || 'mute');
}
/* 计划金额或股数为 0 = 这份计划落库了但一份都买不了 */
function plExecutable(q) {
  if (!q) return { ok: false, why: '旧版本记录没有量化字段' };
  if (!q.position_amount) return { ok: false, why: '可用资金 0 元，计划金额被压成 0' };
  if (!q.total_shares) return { ok: false, why: '上限金额买不满一手，股数取整后为 0' };
  return { ok: true };
}
function plStatusCounts() {
  const o = { 全部: PLANS.length };
  PL_STATUS_ORDER.forEach((k) => {
    o[PL_STATUS_LABEL[k]] = PLANS.filter((p) => p.status === k).length;
  });
  return o;
}
function plOpen(p) { return !!state.plExpand[p.id]; }
function plToggle(id) { state.plExpand[id] = !state.plExpand[id]; }

function plBanner() {
  const todays = PLANS.filter((p) => p.plan_date === PL_TODAY);
  const dead = todays.filter((p) => !plExecutable(plQ(p)).ok);
  const mv = plMv(PL_TODAY), base = PL_BASE_CAPITAL;
  const c2 = Math.round(base * PL_C2_TOTAL * 100) / 100;
  const over = Math.round((mv - c2) * 100) / 100;
  return '<div class="pl-banner ' + (dead.length ? 'bad' : 'ok') + '">' +
    '<div class="pl-banner-main">' +
      '<div class="pl-banner-head">' + icon('plan') +
        '<b>' + PL_TODAY + ' 落了 ' + todays.length + ' 份计划，' +
        (dead.length ? dead.length + ' 份一份都买不了' : '全部可执行') + '</b></div>' +
      '<div class="pl-banner-txt">' +
        (dead.length
          ? '账户当前持仓市值 ' + plMoney(mv) + ' 元，已经超过总仓位红线的 ' + plMoney(c2) + ' 元（基准总资产 ' +
            plMoney(base) + ' × 60%）整整 ' + plMoney(over) + ' 元。量化层按这个差额算可用资金，负数一律归零，' +
            '所以今天新建的计划金额是 0 元、股数 0 股，但状态照样是「待确认」。要真买，先减出额度，' +
            '或者把基准总资产改成你实际入金。'
          : '今天新增的计划都有可用资金承接，可以直接看分档明细。') +
      '</div>' +
      '<div class="pl-banner-acts">' +
        '<button class="btn sm" data-nav="#/holdings">去持仓页看减哪只 ' + icon('arrow', 'sm') + '</button>' +
        '<button class="btn sm" data-nav="#/candidates">回候选池看还有哪些 ' + icon('arrow', 'sm') + '</button>' +
        '<button class="btn link sm" data-nav="#/market-intel?board=regime">先看今天是不是主线行情 ' + icon('arrow', 'sm') + '</button>' +
      '</div>' +
    '</div>' +
    '<div class="pl-banner-side">' +
      ['全 ' + PLANS.length + ' 份', '待确认 ' + (plStatusCounts()['待确认'] || 0) + ' 份',
        '金额归零 ' + PLANS.filter((p) => !plExecutable(plQ(p)).ok).length + ' 份',
        '股数归零 ' + PLANS.filter((p) => { const q = plQ(p); return q && q.position_amount > 0 && !q.total_shares; }).length + ' 份'
      ].map((t) => '<span class="pl-kv">' + esc(t) + '</span>').join('') +
      '<div class="hint">基准总资产 ' + plMoney(base) + ' 元来自配置，持仓页显示的是 ' + plMoney(hdMoneyInt()) +
        ' 元（含浮动盈亏）——两个数不同源，同一个 A 级上限差 ' + plMoney(Math.round((hdMoneyInt() - base) * PL_GRADE_CAP.A)) + ' 元。</div>' +
    '</div>' +
  '</div>';
}
function hdMoneyInt() { return Math.round(hdTotalMv() + hdCash()); }

function plFilterBar(rows) {
  const cnt = plStatusCounts();
  const chips = ['全部'].concat(PL_STATUS_ORDER.map((k) => PL_STATUS_LABEL[k])).map((label) =>
    '<button class="cp-chip ' + ((state.plStatus || '全部') === label ? 'active' : '') + '" data-action="pl-status" data-v="' + esc(label) + '">' +
    esc(label) + '<i class="cp-n">' + (cnt[label] || 0) + '</i></button>').join('');
  const opt = (arr, cur, name, all) => '<select class="input" id="' + name + '">' +
    [all].concat(arr).map((v) => '<option value="' + esc(v) + '"' + (v === cur ? ' selected' : '') + '>' + esc(v) + '</option>').join('') +
    '</select>';
  const f = plFilters();
  const srcOpts = PL_SOURCE_OPTS.map(([label, key]) =>
    '<option value="' + esc(label) + '"' + ((state.plSource || '全部来源') === label ? ' selected' : '') + '>' + esc(label) + '</option>').join('');
  return '<div class="cp-toolbar"><div class="cp-chips">' + chips + '</div></div>' +
    '<div class="pl-filters">' +
      '<label class="pl-fl">计划日期' + opt(plDates(), f.date, 'pl-date', '全部日期') + '</label>' +
      '<label class="pl-fl">综合评级' + opt(['A', 'B', 'C', '未评级'], state.plGrade || '全部评级', 'pl-grade', '全部评级') + '</label>' +
      '<label class="pl-fl">来源<select class="input" id="pl-source">' + srcOpts + '</select></label>' +
      (f.code ? '<button class="cp-chip active" data-action="pl-clear-code">只看 ' +
        esc(f.code + ' ' + ((CANDIDATE_POOL.filter((x) => x.stock_code === f.code)[0] ||
          PLANS.filter((x) => x.stock_code === f.code)[0] || {}).stock_name || '')) + icon('x', 'sm') + '</button>' : '') +
      '<span class="spacer"></span>' +
      '<span class="hint">共 ' + rows.length + ' 条 · 只有综合评级 B 级及以上能生成，C 级或未评级会被后端直接拒绝</span>' +
    '</div>';
}

function plNewForm() {
  if (!state.plNewOpen) return '';
  const pool = CANDIDATE_POOL.map((c) => {
    const g = plGradeOf(c.stock_code);
    return '<option value="' + esc(c.stock_code) + '"' + (state.plGen === c.stock_code ? ' selected' : '') + '>' +
      esc(c.stock_code + ' ' + (c.stock_name || '') + '（' + g + ' ' + (plScore(c.stock_code) ? plScore(c.stock_code).score + '分' : '无评分') + '）') + '</option>';
  }).join('');
  return '<div class="pl-form">' +
    '<div class="pl-form-title">' + icon('plus') + '新建建仓方案</div>' +
    '<div class="pl-form-grid">' +
      '<label class="pl-field">候选池标的（最新一轮）<select class="input" id="pl-new-code">' +
        '<option value="">从候选池选择</option>' + pool + '</select></label>' +
      '<label class="pl-field">或手动输入 6 位代码<input class="input" id="pl-new-manual" maxlength="6" placeholder="例如 600519"' +
        (state.plGen && !CANDIDATE_POOL.some((cc) => cc.stock_code === state.plGen) ? ' value="' + esc(state.plGen) + '"' : '') + '></label>' +
    '</div>' +
    '<div class="pl-form-acts">' +
      '<button class="btn primary sm" data-action="pl-create"' + (state.plBusy ? ' disabled' : '') + '>' +
        (state.plBusy ? '生成中…' : '生成建仓计划（后台）') + '</button>' +
      '<button class="btn sm" data-action="pl-new-close">取消</button>' +
      '<span class="hint">没有评分的标的会先自动跑一次评分再判级；B 级当日已有计划且未满 30 分钟时直接复用旧计划，不会再算一遍。</span>' +
    '</div>' +
  '</div>';
}

function plRowMain(p) {
  const q = plQ(p), sig = plSignal(p), ex = plExecutable(q), drift = plLiveDrift(p);
  const open = plOpen(p);
  const act = p.id;
  let ops = '';
  if (p.status === 'proposed') {
    if (state.plConfirm === 'adopt:' + p.id) {
      ops = '<div class="pl-confirm"><b>采纳这份方案？</b>' +
        '<span>采纳只是把状态改成「已采纳」，系统不会下单，也不会自动转成持仓；成交结果要在持仓页人工登记。</span>' +
        '<span class="row"><button class="btn primary xs" data-action="pl-adopt-ok" data-id="' + act + '">确认采纳</button>' +
        '<button class="btn xs" data-action="pl-confirm-no">取消</button></span></div>';
    } else if (state.plConfirm === 'abandon:' + p.id) {
      ops = '<div class="pl-confirm"><b>放弃这份方案？</b>' +
        '<span>放弃后它仍在列表里，同一天同标的可以再重算出新版本。</span>' +
        '<span class="row"><button class="btn danger xs" data-action="pl-abandon-ok" data-id="' + act + '">确认放弃</button>' +
        '<button class="btn xs" data-action="pl-confirm-no">取消</button></span></div>';
    } else {
      ops = '<span class="row">' +
        '<button class="btn primary xs" data-action="pl-adopt" data-id="' + act + '">采纳</button>' +
        '<button class="btn xs" data-action="pl-abandon" data-id="' + act + '">放弃</button></span>';
    }
  } else if (p.status === 'abandoned' || p.status === 'superseded') {
    ops = '<button class="btn xs ghost" data-action="pl-flip" data-id="' + act + '">改回已采纳</button>';
  } else {
    ops = '<span class="dim">—</span>';
  }
  return '<tr class="pl-tr' + (open ? ' open' : '') + (p.status === 'accepted' ? ' accepted' : '') + '">' +
      '<td><span class="pl-sig ' + sig.tone + '">' + esc(sig.label) + '</span>' +
        (drift && drift.should && drift.should !== sig.label
          ? '<div class="pl-sig-real">按今天价应为' + esc(drift.should) + '</div>' : '') + '</td>' +
      '<td><button class="pl-stock" data-action="pl-expand" data-id="' + act + '">' +
          '<b>' + esc(p.stock_name || p.stock_code) + '</b><span class="mono">' + esc(p.stock_code) + '</span></button>' +
        '<div class="pl-row-sub">' + plGradeTag(p.stock_code) +
          (q && q.reduced ? tag('已降档', 'gold') : '') + (!ex.ok ? tag('不可执行', 'red') : '') + '</div></td>' +
      '<td>' + plStatusTag(p.status) + (p.supersedes_id ? '<div class="pl-row-sub mono">替代 ' + p.supersedes_id + '</div>' : '') +
        '<div class="pl-row-sub"><button class="btn link xs" data-nav="#/candidates?id=' + esc(p.stock_code) + '">候选池里看它</button></div></td>' +
      '<td class="pl-concl">' + esc(plConclusion(p)) + '</td>' +
      '<td class="num">' + (q ? plMoney(q.position_amount) + ' 元' : '—') +
        '<div class="pl-row-sub">' + (q ? q.total_shares + ' 股' : '—') + '</div></td>' +
      '<td class="num">' + (q ? plPct(q.position_cap_pct, 0) : '—') +
        '<div class="pl-row-sub">总仓 ' + (q && q.expected_total_pct != null ? plPct(q.expected_total_pct) : '—') + '</div></td>' +
      '<td class="num mono">' + (q ? q.initial_stop : p.stop_loss) + ' / ' + (q ? q.take_profit : p.take_profit) + '</td>' +
      '<td class="num">' + (q && q.breakeven_ratio != null
        ? '<span class="' + (q.breakeven_ok ? '' : 'warn-txt') + '">' + q.breakeven_ratio + ':1</span>' : '—') + '</td>' +
      '<td>' + tag(PL_SOURCE_LABEL[p.source || 'manual'] || p.source, p.source === 'candidate' ? 'blue' : 'mute') +
        '<div class="pl-row-sub">' + esc(String(p.created_at || '').slice(5, 16)) + '</div></td>' +
      '<td>' + ops + '</td>' +
    '</tr>' +
    (open ? '<tr class="pl-detail-tr"><td colspan="10">' + plDetail(p) + '</td></tr>' : '');
}

function plKv(label, value, cls) {
  return '<div class="pl-kv2"><span>' + esc(label) + '</span><b class="' + (cls || '') + '">' + value + '</b></div>';
}

function plDetail(p) {
  const q = plQ(p), ex = plExecutable(q), drift = plLiveDrift(p);
  const chain = plChain(p);
  const dims = p.dimensions || [];
  const s = plScore(p.stock_code);
  const sec1 = '<div class="card pl-sec"><div class="card-title"><h3>重算与数据时效</h3>' +
      '<span class="hint">重算会生成新版本，同标的同交易日的旧「待确认」自动被替代</span></div>' +
      '<div class="row" style="flex-wrap:wrap;gap:8px">' +
        '<button class="btn sm" data-action="pl-recalc" data-id="' + p.id + '"' + (state.plBusy ? ' disabled' : '') + '>' +
          icon('rotate', 'sm') + (state.plBusyId === p.id ? '重算中…' : '重算本计划') + '</button>' +
        (q ? plFreshTag(q.freshness) : tag('无量化字段', 'mute')) +
        '<span class="hint">数据截至 ' + esc((q && q.data_as_of) || '未记录') + '</span>' +
        '<span class="hint">价格快照日 ' + esc((q && q.price_date) || '—') + '，今天 ' + esc(PL_TODAY) + '</span>' +
        (drift ? '<span class="hint">现价 ' + drift.live + '（' + (drift.pct > 0 ? '+' : '') + drift.pct + '%）</span>' : '') +
      '</div>' +
      '<div class="cap-note" style="margin-top:10px">' + icon('info') + '<div><b>版本链：</b>' +
        (chain.length > 1
          ? chain.map((c) => '<span class="mono">#' + c.id + '</span> ' + PL_STATUS_LABEL[c.status] + '（' + esc(String(c.created_at || '').slice(11, 16)) + '）').join(' → ')
          : '这一只当天只有这一份计划') + '。' +
        '接口返回里已采纳的版本会保留，被替代的只改状态不删除。</div></div>' +
    '</div>';
  const sec2 = q ? '<div class="card pl-sec"><div class="card-title"><h3>仓位分配（按账户真实资金算出来的数）</h3>' +
      (ex.ok ? '<span class="hint">可执行</span>' : '<span class="tag red">不可执行：' + esc(ex.why) + '</span>') + '</div>' +
      '<div class="pl-grid">' +
        plKv('计划当时收盘价', (q.current_price ?? '—') + ' 元') +
        plKv('今天价格', (drift ? drift.live : '—') + ' 元') +
        plKv('单票仓位上限', plPct(q.position_cap_pct, 0) + '（' + esc(q.grade || '—') + ' 级档）') +
        plKv('仓位金额', plMoney(q.position_amount) + ' 元', ex.ok ? '' : 'warn-txt') +
        plKv('可买股数', q.position_shares + ' 股') +
        plKv('账户可用资金', plMoney(q.available_capital) + ' 元', q.available_capital ? '' : 'warn-txt') +
        plKv('成本基准（第一档区间中点）', q.cost_basis + ' 元') +
        plKv('初始止损', q.initial_stop + ' 元') +
        plKv('成本 × 0.92 硬止损', q.c3_stop + ' 元') +
        plKv('第一止盈', q.take_profit + ' 元') +
        plKv('盈亏比', (q.breakeven_ratio ?? '—') + ':1', q.breakeven_ok ? '' : 'warn-txt') +
        plKv('建仓后总仓位', q.expected_total_pct != null ? plPct(q.expected_total_pct) : '—') +
        plKv('分档取整差额', plMoney(q.rounding_gap) + ' 元') +
      '</div>' +
      ((q.notes && q.notes.length) || q.lot_short ? '<div class="pl-notes"><b>量化层留下的说明（正式页面目前一条都不显示）</b>' +
        (q.notes || []).map((n) => '<div>· ' + esc(n) + '</div>').join('') +
        (q.lot_short ? '<div>· 有 ' + q.lot_short + ' 个档位金额买不满一手，股数取整后是 0 股。</div>' : '') +
        (!q.breakeven_ok && q.breakeven_ratio != null && !q.reduced ? '<div>· 盈亏比 ' + q.breakeven_ratio + ':1 低于 3:1 门槛，属于要重点盯止损的那类。</div>' : '') +
        '</div>' : '') +
    '</div>' : '<div class="card pl-sec"><div class="card-title"><h3>仓位分配</h3></div>' +
      '<div class="empty-list"><strong>这条是 v3.0 之前生成的旧记录，没有量化字段</strong>' +
      '只有大模型给的比例明细，金额、股数、止损止盈都要重算一遍才有。正式页面遇到这种记录会整块空掉，这里把明细照原样留着。</div></div>';
  const bl = (q && q.batches && q.batches.length) ? q.batches : (p.batches || []);
  const sec3 = '<div class="card pl-sec"><div class="card-title"><h3>分档买入明细</h3>' +
      '<span class="hint">' + (q && q.batches && q.batches.length ? '金额、股数由量化层按上限重算，比例做过归一化' : '旧数据：只有大模型给的资金占比') + '</span></div>' +
      (bl.length ? '<div class="table-wrap"><table><thead><tr><th>批次</th><th>价格区间</th><th>触发条件</th>' +
        '<th class="num">' + (q && q.batches && q.batches.length ? '金额' : '资金占比%') + '</th>' +
        (q && q.batches && q.batches.length ? '<th class="num">股数</th><th class="num">累计占比</th>' : '') +
        '</tr></thead><tbody>' + bl.map((b) => '<tr>' +
          '<td>' + esc(b.tranche) + '</td><td class="mono">' + esc(b.price_zone) + '</td>' +
          '<td class="small">' + esc(b.trigger_note) + '</td>' +
          '<td class="num">' + (b.amount != null ? plMoney(b.amount) + ' 元' : (b.ratio_pct ?? '—') + '%') + '</td>' +
          (q && q.batches && q.batches.length
            ? '<td class="num">' + (b.shares ? b.shares + ' 股' : '<span class="warn-txt">0 股</span>') + '</td>' +
              '<td class="num">' + (b.cum_pct ?? '—') + '%</td>' : '') +
          '</tr>').join('') + '</tbody></table></div>' +
        (q ? (q.total_shares
          ? '<div class="pl-sum">合计投入 <b>' + plMoney(q.total_amount) + ' 元</b>，合计持股 <b>' + plMoney(q.total_shares) + ' 股</b>，' +
            '不超过单票分级上限 ' + plPct(q.position_cap_pct, 0) + '；分档金额与上限之间差 ' + plMoney(q.rounding_gap) + ' 元（每档按一手取整抹掉的）。' +
            (q.lot_short ? '其中 ' + q.lot_short + ' 档金额买不满一手，只能靠后面几档补。' : '') + '</div>'
          : '<div class="pl-sum warn-txt">' + (q.total_amount
              ? '计划投入有 ' + plMoney(q.total_amount) + ' 元，但每一档按一手取整后都是 0 股——单价 ' + q.current_price +
                ' 元，一手要 ' + plMoney(Math.round(q.current_price * PL_LOT)) + ' 元，比这一档的金额还大。'
              : '合计 0 元 0 股：可用资金是 0，这份计划落库了但一股都买不了——' + esc((q.notes && q.notes[0]) || '') + '。') + '</div>') : '')
        : '<div class="empty-list">这条没有分批明细。</div>') +
    '</div>';
  const sec4 = '<div class="card pl-sec"><div class="card-title"><h3>止盈止损与仓位红线</h3></div>' +
      '<div class="pl-rules">' +
        '<div><b>止损</b><span>初始止损 ' + ((q && q.initial_stop) || p.stop_loss || '—') +
          '，取「大模型给的止损」和「成本 × 0.92」里更靠上的那个，跌破无条件离场。</span></div>' +
        '<div><b>止盈</b><span>第一目标 ' + ((q && q.take_profit) || p.take_profit || '—') +
          ' 减 1/3，第二目标再减 1/3，之后按移动止盈跟。</span></div>' +
        '<div><b>单票上限</b><span>' + plPct(q ? q.position_cap_pct : 0, 0) +
          ' 是评级对应的分级上限（A 30% / B 20% / C 10%），不是集中度告警线。</span></div>' +
        '<div><b>集中度告警</b><span>单只占总资产到 ' + PL_C1_CONCENTRATION + '% 会单独告警，和上一行是两个东西。</span></div>' +
        '<div><b>总仓位</b><span>账户整体不超过 ' + Math.round(PL_C2_TOTAL * 100) + '%，今天实际 ' +
          plPct(q ? (q.account_mv / q.total_capital) * 100 : 0) + '。</span></div>' +
      '</div></div>';
  const sec5 = '<div class="card pl-sec"><div class="card-title"><h3>市场强弱与建仓逻辑</h3></div>' +
      '<div class="pl-prose">' + esc(p.market_regime || '（这条没落市场强弱）') + '</div>' +
      '<div class="pl-prose">' + esc(p.rationale || '（无）') + '</div>' +
      '<div class="row"><button class="btn link xs" data-nav="#/market-intel?board=regime">看这天的结构判定怎么来的 ' + icon('arrow', 'sm') + '</button></div>' +
    '</div>';
  const sec6 = '<div class="card pl-sec"><div class="card-title"><h3>生成依据</h3>' +
      '<span class="hint">评分与「评分报告」页同源，本页不再算一遍</span></div>' +
      '<div class="detail-tags">' + plGradeTag(p.stock_code) +
        (s ? '<span class="hint">评分日 ' + esc(s.score_date) + '，距今天 ' + s.age + ' 个交易日' +
          (s.age > PL_SCORE_MAX_DAYS ? '（已超过 ' + PL_SCORE_MAX_DAYS + ' 日，按未评级处理）' : '') + '</span>' : '<span class="hint">没有评分记录</span>') +
      '</div>' +
      (s && s.risk && s.risk.length ? '<div class="pl-risks"><b>风险提示</b>' +
        s.risk.map((r) => '<div>· ' + esc(r) + '</div>').join('') + '</div>'
        : '<div class="hint">这一轮没有输出风险提示。</div>') +
      (dims.length ? '<div class="stack" style="margin-top:12px">' + dims.map((d) => {
        const v = d.verdict === '支持' ? 'var(--up)' : d.verdict === '风险' ? 'var(--warn)' : 'var(--text-3)';
        return '<div class="pl-dim"><span class="pl-dim-name">' + esc(d.dim) + '</span>' +
          '<span class="conf-bar"><span class="conf-fill" style="width:' + Math.max(0, Math.min(100, d.score)) + '%;background:' + v + '"></span></span>' +
          '<span class="mono pl-dim-score">' + d.score + '</span>' + tag(d.verdict || '中性', d.verdict === '支持' ? 'green' : d.verdict === '风险' ? 'gold' : 'mute') +
          '<span class="pl-dim-adv">' + esc(d.advice || '') + '</span></div>';
      }).join('') + '</div>' : '<div class="hint" style="margin-top:10px">旧记录没有维度归因。</div>') +
      (p.final_advice ? '<div class="hd-concl" style="margin-top:12px"><div class="hd-concl-txt">' + esc(p.final_advice) + '</div></div>' : '') +
    '</div>';
  return '<div class="pl-detail">' + sec1 + sec2 + sec3 + sec4 + sec5 + sec6 + '</div>';
}

const PL_NOTES = [
  ['先说能不能买，再说怎么买', '列表第一列不是股票而是「信号 + 能不能执行」，金额那一列直接给股数。原页面把「待确认」放在最显眼的位置，但账户没有额度时「待确认」是没有意义的状态。'],
  ['把量化层藏起来的字段全部摊开', '可用资金、C3 硬止损、价格快照日、盈亏比是否达标、降档说明这几项后端早就算好了，正式页面一个都没显示。缺哪一条，用户对不上账就只能猜。'],
  ['信号同时给两个口径', '「按生成当时价」是后端算的，「按今天价」是本页按现价重算的，两个并排显示，用户才知道这栏标签不会跟着行情走。'],
  ['采纳 / 放弃就地做，且说清不下单', '点采纳先出内联确认，写明不会下单、不会自动转持仓，成交要在持仓页人工登记；同一时间只允许一个生成任务，连点不会落重复计划。'],
  ['重算一定生成新版本', '旧的待确认自动转「已被新版本替代」，已采纳保留，版本链在详情第一段能看见；历史日期的方案重算不了，toast 直接说明原因。'],
  ['两个「C1」分开写', '分级上限（A 30% / B 20% / C 10%）和单只占总资产 60% 的集中度告警线是两件事，原页面混用一个名字，这里拆成两行。']
];
function plNoteCard() {
  const open = state.plNoteOpen;
  return '<div class="card"><div class="card-title"><h3>这一页为什么这样做</h3>' +
      '<span class="hint">和正式建仓计划页的六处差别，验收时对照</span>' +
      '<button class="btn link sm" data-action="pl-note">' + (open ? '收起' : '展开') + '</button></div>' +
      (open ? '<div class="stack">' + PL_NOTES.map((x) =>
        '<div class="mi-gap"><b>' + esc(x[0]) + '</b><p>' + esc(x[1]) + '</p></div>').join('') + '</div>'
        : '<div class="hint">展开看每一条的设计理由。</div>') + '</div>';
}
function plGapCard() {
  const open = state.plGapOpen;
  return '<div class="card"><div class="card-title"><h3>对着后端代码核过的落地缺口</h3>' +
      '<span class="hint">' + PL_GAPS.length + ' 条，全部指向真实函数行为，不是设想</span>' +
      '<button class="btn link sm" data-action="pl-gap">' + (open ? '收起' : '展开') + '</button></div>' +
      (open ? '<div class="stack">' + PL_GAPS.map((g) =>
        '<div class="mi-gap"><b>' + esc(g[0]) + '</b><p>' + esc(g[1]) + '</p></div>').join('') + '</div>'
        : '<div class="hint">展开看每一条的原因、影响和验收口径。</div>') + '</div>';
}

function renderPlans() {
  const rows = plRows();
  const f = plFilters();
  const busy = state.plBusy;
  return '<div class="page-head"><div>' +
      '<div class="page-title">建仓计划</div>' +
      '<div class="page-sub">候选池打到 B 级以上才会落这份计划。大模型只给价格区间和资金配比，金额、股数、止损止盈、总仓位全部由量化层按账户真实资金和风控红线重算。采纳只改状态，系统不下单。</div>' +
    '</div><div class="page-actions">' +
      '<button class="btn primary sm" data-action="pl-new-open">' + icon('plus', 'sm') + '新建建仓方案</button>' +
      '<button class="btn sm" data-action="pl-pipeline"' + (busy ? ' disabled' : '') + '>' + icon('workflow', 'sm') + '重算今日 B 级以上候选</button>' +
      '<button class="btn sm" data-action="pl-refresh">' + icon('rotate', 'sm') + '刷新</button>' +
    '</div></div>' +
    plBanner() + plNewForm() + plFilterBar(rows) +
    (rows.length ? '<div class="card"><div class="table-wrap"><table>' +
        '<thead><tr><th>信号</th><th>标的</th><th>状态</th><th>计划结论</th><th class="num">仓位金额</th>' +
        '<th class="num">单票上限</th><th class="num">止损 / 止盈</th><th class="num">盈亏比</th><th>来源</th><th></th></tr></thead><tbody>' +
        rows.map(plRowMain).join('') + '</tbody></table></div>' +
        '<div class="cap-note">' + icon('alert') + '<div>「监控中 / 止盈已触发 / 止损已触发」判断用的是<b>计划生成当时冻结的收盘价</b>，不会跟今天的行情变。' +
          '列表右侧标出的「按今天价应为」是本页按现价重算的结果，正式页面没有这一栏。</div></div></div>'
      : '<div class="card"><div class="empty-list"><strong>' +
        (f.code ? f.code + ' 还没有建仓计划' : '这组筛选条件下没有计划') + '</strong>' +
        (f.code ? '建仓计划只对综合评级 B 级及以上的标的开放；没有评分的标的，生成时会先自动跑一次评分再判级。' : '换个日期或评级，或者直接新建一份。') +
        '每天 16:10 的候选池链路会自动给 B 级以上的标的生成计划。' +
        (f.code ? '<div class="row" style="margin-top:12px"><button class="btn primary sm" data-action="pl-create-one" data-code="' + esc(f.code) + '">' +
          icon('plan', 'sm') + '给 ' + esc(f.code) + ' 生成建仓方案</button>' +
          '<button class="btn sm" data-nav="#/candidates?id=' + esc(f.code) + '">回候选池看它的上下文 ' + icon('arrow', 'sm') + '</button></div>' : '') +
        '</div></div>') +
    plNoteCard() + plGapCard();
}

function syncPlansHash() {
  if (state.route !== '#/plans') return;
  const f = plFilters();
  let next = '#/plans?status=' + encodeURIComponent(f.status) + '&date=' + encodeURIComponent(f.date) +
    '&grade=' + encodeURIComponent(f.grade) + '&source=' + encodeURIComponent(f.source);
  if (f.code) next += '&code=' + encodeURIComponent(f.code);
  const openIds = Object.keys(state.plExpand).filter((k) => state.plExpand[k]);
  if (openIds.length) next += '&id=' + openIds.join(',');
  if (location.hash !== next) history.replaceState(null, '', next);
}

function plFind(id) { return PLANS.find((x) => String(x.id) === String(id)); }

/* 无评分标的的确定性判级：同一串代码永远得到同一档，方便复现 */
function plFakeGrade(code) {
  let h = 0;
  for (let k = 0; k < code.length; k++) h = (h * 31 + code.charCodeAt(k)) % 100;
  return h < 34 ? { grade: 'A', score: 85 + (h % 5) } : h < 67 ? { grade: 'B', score: 78 + (h % 5) } : { grade: 'C', score: 62 + (h % 10) };
}

function handlePlansAction(action, el) {
  const id = el.dataset.id;
  if (action === 'pl-refresh') { renderView(); toast('已刷新', '列表按当前筛选重新拉了一遍。', 'info'); return; }
  if (action === 'pl-gap') { state.plGapOpen = !state.plGapOpen; renderView(); return; }
  if (action === 'pl-note') { state.plNoteOpen = !state.plNoteOpen; renderView(); return; }
  if (action === 'pl-status') { state.plStatus = el.dataset.v; renderView(); syncPlansHash(); return; }
  if (action === 'pl-clear-code') { state.plCode = ''; state.plDate = ''; renderView(); syncPlansHash(); return; }
  if (action === 'pl-create-one') {
    state.plNewOpen = true; state.plGen = el.dataset.code; state.plDate = PL_TODAY;
    renderView();
    const m = $('#pl-new-manual'); if (m) { m.value = el.dataset.code; m.focus(); }
    toast('已带上标的', el.dataset.code + ' 已填进新建表单，点「生成」才会真的跑判级。', 'info');
    return;
  }
  if (action === 'pl-expand') { plToggle(id); renderView(); syncPlansHash(); return; }
  if (action === 'pl-new-open') { state.plNewOpen = !state.plNewOpen; renderView(); return; }
  if (action === 'pl-new-close') { state.plNewOpen = false; renderView(); return; }
  if (action === 'pl-confirm-no') { state.plConfirm = null; renderView(); return; }
  if (action === 'pl-adopt') { state.plConfirm = 'adopt:' + id; renderView(); return; }
  if (action === 'pl-abandon') { state.plConfirm = 'abandon:' + id; renderView(); return; }
  if (action === 'pl-adopt-ok') {
    const p = plFind(id); state.plConfirm = null;
    if (!p) { renderView(); return; }
    p.status = 'accepted';
    state.plExpand[p.id] = true;
    renderView(); syncPlansHash();
    toast('已采纳 # ' + p.id, '状态改完了。系统不会下单，也不会自动转成持仓——真买了要去持仓页人工登记成交。', 'ok');
    return;
  }
  if (action === 'pl-abandon-ok') {
    const p = plFind(id); state.plConfirm = null;
    if (!p) { renderView(); return; }
    p.status = 'abandoned';
    renderView(); syncPlansHash();
    toast('已放弃 # ' + p.id, '这条留档，同一天可以再重算出新版本。', 'info');
    return;
  }
  if (action === 'pl-flip') {
    const p = plFind(id);
    if (!p) return;
    p.status = 'accepted';
    renderView(); syncPlansHash();
    toast('已改成已采纳（后端不拦）', '接口只校验状态值合不合法，不校验从哪来、也不查同一标的同一天是否已有生效版本。于是 ' +
      p.stock_name + ' ' + p.plan_date + ' 这天可能同时挂着两份「已采纳」。落地要补状态机与唯一性校验。', 'warn');
    return;
  }
  if (action === 'pl-recalc' || action === 'pl-create') {
    if (state.plBusy) { toast('上一条还在跑', '同一时间只允许一个建仓任务，避免同一标的落两份计划。', 'info'); return; }
    let code = '', name = '';
    if (action === 'pl-recalc') {
      const src = plFind(id);
      if (!src) return;
      code = src.stock_code; name = src.stock_name;
    } else {
      const manual = (($('#pl-new-manual') || {}).value || '').trim();
      const picked = (($('#pl-new-code') || {}).value || '').trim();
      if (manual) {
        if (!/^\d{6}$/.test(manual)) { toast('代码不对', '要 6 位数字股票代码。', 'bad'); return; }
        code = manual;
        const c = CANDIDATE_POOL.find((x) => x.stock_code === manual);
        name = c ? c.stock_name : manual;
      } else if (picked) {
        code = picked;
        const c = CANDIDATE_POOL.find((x) => x.stock_code === picked);
        name = c ? c.stock_name : picked;
      } else { toast('还没选标的', '从候选池挑一只，或者输入 6 位代码。', 'bad'); return; }
    }
    state.plBusy = true; state.plBusyId = action === 'pl-recalc' ? Number(id) : null;
    renderView();
    /* 没有评分先自动跑一次评分（router.py:141-145），再判级 */
    const needScore = !plScore(code);
    if (needScore) {
      setTimeout(() => {
        const g = plFakeGrade(code);
        PL_SCORES[code] = { grade: g.grade, score: g.score, score_date: PL_TODAY, age: 0,
          risk: ['原型内按代码确定性生成的评分，正式系统由评分链路产出'] };
        state.plBusy = false; state.plBusyId = null;
        toast('评分完成', code + ' 原判级 ' + g.grade + ' 级 ' + g.score + ' 分，现在按这个评级继续判建仓门槛。', 'info');
        plGate(code, name, action === 'pl-recalc' ? plFind(id) : null);
      }, 1100);
      return;
    }
    setTimeout(() => { state.plBusy = false; state.plBusyId = null; plGate(code, name, action === 'pl-recalc' ? plFind(id) : null); }, 650);
    return;
  }
  if (action === 'pl-pipeline') {
    if (state.plBusy) { toast('上一条还在跑', '批量重算同一时间只允许一个。', 'info'); return; }
    state.plBusy = true; renderView();
    setTimeout(() => {
      state.plBusy = false;
      const list = ['603501', '688981', '000725'];
      const made = []; const refused = [];
      list.forEach((c) => {
        const s = plScore(c) || plFakeGrade(c);
        PL_SCORES[c] = PL_SCORES[c] || { grade: s.grade, score: s.score, score_date: PL_TODAY, age: 0, risk: [] };
        const g = plGradeOf(c);
        if (g === 'A' || g === 'B') made.push(plUpsert(c, (CANDIDATE_POOL.find((x) => x.stock_code === c) || {}).stock_name || c, 'candidate'));
        else refused.push(c + '（' + g + '）');
      });
      renderView(); syncPlansHash();
      toast('今日联动完成', '候选池 B 级以上 ' + made.length + ' 只已出计划' +
        (refused.length ? '；' + refused.join('、') + ' 评级不足被拒绝' : '') +
        '。可用资金仍是 0 元，所以金额还是被压成 0。', made.length ? 'ok' : 'warn');
    }, 1300);
    return;
  }
}

/* 建仓门槛：评级不足直接拒绝，B 级 30 分钟缓存命中就复用（router.py:141-167） */
function plGate(code, name, srcPlan) {
  const g = plGradeOf(code);
  if (g !== 'A' && g !== 'B') {
    renderView();
    toast('评级不足，未生成', '评级不足（当前 ' + g + '），暂不生成建仓计划；仅 B 级及以上评级标的可生成，可先在「评分报告」页完成/确认评分。', 'bad');
    return;
  }
  if (g === 'B') {
    const hit = PLANS.filter((p) => p.stock_code === code && p.plan_date === PL_TODAY && p.status !== 'superseded')
      .sort((a, b) => b.id - a.id)[0];
    if (hit && (!srcPlan || srcPlan.status === 'proposed' || srcPlan.id === hit.id)) {
      state.plExpand[hit.id] = true;
      renderView(); syncPlansHash();
      toast('命中 B 级 30 分钟缓存', '当天已有计划且没超过半小时，直接复用 #' + hit.id + '，没调模型。' +
        '但计划记录本身没有任何变化，时效字段仍写「当日数据截至」——用户看不出这是半小时前那份。落地要补缓存命中标记。', 'warn');
      return;
    }
  }
  const row = plUpsert(code, name, srcPlan ? (srcPlan.source || 'manual') : 'manual');
  const fromHist = srcPlan && srcPlan.plan_date !== PL_TODAY;
  state.plNewOpen = false; state.plGen = '';
  state.plExpand[row.id] = true;
  state.plDate = PL_TODAY; state.plStatus = '全部';
  renderView(); syncPlansHash();
  const q = plQ(row);
  toast('已生成 #' + row.id, row.stock_name + ' 建仓计划落库：上限 ' + plPct(q.position_cap_pct, 0) + '、金额 ' + plMoney(q.position_amount) +
    ' 元、' + q.total_shares + ' 股。' + (q.position_amount ? '' : '可用资金为 0，这份买不了。') +
    (row.supersedes_id ? '原「待确认」#' + row.supersedes_id + ' 已标记为已被新版本替代。' : '') +
    (fromHist ? '注意：重算只能按今天（' + PL_TODAY + '）生成，#' + srcPlan.id + ' 那份 ' + srcPlan.plan_date + ' 的计划不受影响。' : ''), 'ok');
}

/* 落一份新计划：同标的同交易日的待确认版本转为已被新版本替代 */
function plUpsert(code, name, source) {
  const close = (PL_CLOSE_AT[PL_TODAY] || {})[code] || [null, null];
  const price = Number(close[0] || PL_LIVE_NOW[code] || 0);
  const s = plScore(code) || { grade: 'B', score: 78 };
  const g = plGradeOf(code);
  const old = PLANS.filter((p) => p.stock_code === code && p.plan_date === PL_TODAY && p.status === 'proposed').sort((a, b) => b.id - a.id)[0];
  const base = price ? Math.round(price * 100) / 100 : 100;
  const f = (v) => Math.round(v * 100) / 100;
  const id = Math.max.apply(null, PLANS.map((p) => p.id)) + 1;
  const row = {
    id: id, stock_code: code, stock_name: name || code, plan_date: PL_TODAY,
    status: 'proposed', source: source || 'manual', supersedes_id: old ? old.id : null,
    created_at: PL_TODAY + ' ' + String(9 + (id % 6)).padStart(2, '0') + ':' + String((id * 7) % 60).padStart(2, '0') + ':00',
    total_pct: Math.round((PL_GRADE_CAP[g] || PL_CAP_FALLBACK) * 100),
    stop_loss: f(base * 0.93), take_profit: f(base * 1.14),
    batches: [
      { tranche: '第一档', price_zone: f(base * 0.985) + ' - ' + f(base * 1.0), ratio_pct: 50, trigger_note: '回踩不破 5 日线，量比不低于 0.8 时首仓' },
      { tranche: '第二档', price_zone: f(base * 1.0) + ' - ' + f(base * 1.02), ratio_pct: 30, trigger_note: '放量站上前一日高点' },
      { tranche: '第三档', price_zone: f(base * 1.025) + ' - ' + f(base * 1.045), ratio_pct: 20, trigger_note: '所属板块同步走强才补，不追单只独涨' }
    ],
    rationale: '原型内按同一套量化规则补算的区间与配比；正式系统这一段来自大模型，数值仍由量化层重算。',
    market_regime: '半导体仍是榜面连续居前的主线，结构处于确认段；今日大盘量能未再放大，第三档要等板块同步。',
    dimensions: [
      { dim: '趋势', score: 78, verdict: '支持', advice: '站稳前高才开第二档。' },
      { dim: '资金', score: 70, verdict: '支持', advice: '主力净流入连续但金额在缩。' },
      { dim: '题材', score: 74, verdict: '支持', advice: '产业逻辑与情绪各占一半。' },
      { dim: '风险', score: 46, verdict: '风险', advice: '拥挤度偏高，不追高开。' }
    ],
    final_advice: (g === 'A' ? 'A 级' : 'B 级') + '，上限 ' + Math.round((PL_GRADE_CAP[g] || PL_CAP_FALLBACK) * 100) +
      '%；当前账户已超总仓位红线，先减出额度再按档介入。',
    synthetic: true, _snapClose: close[1] || PL_TODAY
  };
  PL_SCORES[code] = PL_SCORES[code] || { grade: s.grade, score: s.score, score_date: PL_TODAY, age: 0, risk: ['原型内合成评分'] };
  if (price && !PL_CLOSE_AT[PL_TODAY][code]) PL_CLOSE_AT[PL_TODAY][code] = [price, PL_TODAY];
  PL_CLOSE_AT[PL_TODAY][code] = PL_CLOSE_AT[PL_TODAY][code] || [base, PL_TODAY];
  PL_LIVE_NOW[code] = PL_LIVE_NOW[code] || base;
  if (old) old.status = 'superseded';
  PLANS.unshift(row);
  return row;
}

function renderView() {
  const route = state.route;
  let html = '';
  if (route === '#/overview') html = renderWorkspaceOverview();
  else if (route === '#/candidates') html = renderCandidates();
  else if (route === '#/holdings') html = renderHoldings();
  else if (route === '#/paper') html = renderPaper();
  else if (route === '#/reviews') html = renderReviews();
  else if (route === '#/experience') html = renderExperience();
  else if (route === '#/market-intel') html = renderMarketIntel();
  else if (route === '#/plans') html = renderPlans();
  else if (route.startsWith('#/system/')) {
    const key = govTabKey();
    if (key === 'overview') html = renderOverview();
    else if (key === 'rules') html = renderRules();
    else if (key === 'factors') html = renderFactors();
    else if (key === 'capability') html = renderCapability();
    else html = renderOverview();
  } else {
    const info = PLACEHOLDERS[route];
    html = info ? renderPlaceholder(info) : renderWorkspaceOverview();
  }
  $('#view').innerHTML = html;
  hydrateIcons($('#view'));
  bindPage();
  if (route === '#/overview') woEnsureTicker();
  if (state.miDrawerPending && state.miSector) {
    state.miDrawerPending = false;
    openDrawer('mi-sector', state.miSector);
  }
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
  const plDate = $('#pl-date');
  if (plDate) plDate.addEventListener('change', (e) => { state.plDate = e.target.value; renderView(); syncPlansHash(); });
  const plGrade = $('#pl-grade');
  if (plGrade) plGrade.addEventListener('change', (e) => { state.plGrade = e.target.value; renderView(); syncPlansHash(); });
  const plSource = $('#pl-source');
  if (plSource) plSource.addEventListener('change', (e) => { state.plSource = e.target.value; renderView(); syncPlansHash(); });

  const miSel = $('#mi-date');
  if (miSel) miSel.addEventListener('change', (e) => {
    state.miDate = e.target.value;
    state.miSector = null;
    closeDrawer();
    renderView();
    syncMarketIntelHash();
  });
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
      '<li><b>按交易节奏分组：</b>今日 → 研究 → 计划 → 复盘 → 系统。左侧从 17 项压到 12 项，先解决「每天先看什么」；行业消息雷达、游资追踪、交易知识库按实际使用反馈移出导航。</li>' +
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
  } else if (kind === 'hd-new') {
    title = '录入人工建仓';
    sub = '系统不自动下单：这里只记录你已经成交的结果';
    body = hdNewFormHtml(state.hdNewPending ? state.hdNewPending.v : (payload || {}), state.hdNewPending ? state.hdNewPending.warns : null);
  } else if (kind === 'hd-ocr') {
    title = 'OCR 截图建仓';
    sub = '上传券商持仓截图，识别结果必须人工核对后才写入';
    body = hdOcrFormHtml();
  } else if (kind === 'hd-baseline') {
    title = '账户基线';
    sub = '总资产与可用现金决定总仓位口径；改完下面的红线判定会跟着变';
    body = hdBaselineFormHtml();
  } else if (kind === 'pp-new') {
    title = '新建模拟账户';
    sub = 'AI 自主下单只在隔离账本里发生，不碰真实资产';
    body = ppNewFormHtml(state.ppForm && state.ppForm.kind === 'new' ? state.ppForm : (payload || {}), state.ppForm ? state.ppForm.errs : null);
  } else if (kind === 'pp-research') {
    title = '手动研究取证';
    sub = '证据与工具轨迹会写进模拟账户的研究记录';
    body = ppResearchFormHtml(state.ppForm && state.ppForm.kind === 'research' ? state.ppForm : (payload || {}), state.ppForm ? state.ppForm.errs : null);
  } else if (kind === 'pp-archive') {
    const acc = payload && payload.id ? payload : ppAcc();
    title = '归档模拟账户';
    sub = '归档后调度停止，历史保留且只读';
    body = ppArchiveFormHtml(acc, state.ppForm, state.ppForm ? state.ppForm.errs : null);
  } else if (kind === 'tasks') {
    const running = state.rules.filter((r) => r.audit === 'auditing');
    title = '任务中心';
    sub = running.length ? running.length + ' 个后台任务进行中' : '暂时没有后台任务';
    body = (running.length ?
      '<div class="stack">' + running.map((r) =>
        '<div class="audit-card"><div class="row"><b>' + esc(r.name) + '</b><span class="spacer"></span><span class="state run">审核中</span></div>' +
          '<div class="progress"><div class="progress-bar"></div></div>' +
          '<div class="small muted">第 ' + (r.round || 1) + ' 轮建议审核 · 完成后自动进入「等你决定」，无需守着页面。</div></div>'
      ).join('') + '</div>' +
      '<div class="cap-note" style="margin-top:14px">' + icon('info') + '<div>接入后端后，这里会显示建议审核、因子回测、建仓方案生成等任务的真实进度与失败重试入口。</div></div>'
      :
      '<div class="empty-list"><strong>没有运行中的任务</strong>提交批量审核或重新审核后，任务进度会显示在这里。</div>' +
      '<div class="cap-note" style="margin-top:14px">' + icon('clock') + '<div>正式接入后，建议审核（生产任务名：建议辩证审核 / 单条建议辩证审核）、因子回测、建仓方案生成等后台任务会在这里显示进度，并在完成时通知当前页面刷新。</div></div>');
  } else if (kind === 'mi-sector') {
    title = payload + ' · 板块判定链路';
    sub = miDate() + ' 快照 → 结构 → 前瞻 → 归因 → 后验';
    body = miSectorDrawerHtml(payload);
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
  toast('已提交批量审核', '共 ' + targets.length + ' 条建议进后台队列（一次只跑 1 个），完成后自动刷新。', 'info');
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
  /* ---- 工作台总览：就地展开 / 今日标记 / 补跑与队列（只动本页展示，不写业务数据）---- */
  if (action === 'wo-scroll-todo' || action === 'wo-reveal-tasks' || action === 'wo-reveal-schedule') {
    if (action === 'wo-reveal-tasks') state.woReveal.tasks = !state.woReveal.tasks;
    if (action === 'wo-reveal-schedule') state.woReveal.schedule = !state.woReveal.schedule;
    renderView();
    const anchor = document.querySelector('#' + (action === 'wo-scroll-todo' ? 'wov-todo' : 'wov-data'));
    if (anchor) anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }
  if (action === 'wo-toggle-only') { state.woOnlyTodo = !state.woOnlyTodo; renderView(); return; }
  if (action === 'wo-reveal-group') {
    const gid = el.dataset.group;
    state.woReveal['g:' + gid] = !state.woReveal['g:' + gid];
    renderView();
    return;
  }
  if (action === 'wo-done-group') {
    const gid = el.dataset.group;
    if (state.woDone[gid]) {
      delete state.woDone[gid];
      renderView();
      toast('已撤下标记', '这一组重新展开，条目一条没少。', 'info');
      return;
    }
    const grp = woTodoGroups().filter(function (x) { return x.id === gid; })[0];
    const map = state.woDone[gid] = {};
    if (grp) grp.items.forEach(function (i) { map[i.id] = true; });
    renderView();
    toast('这一组今天收起', '只是把这张牌折起来，方便看清剩下的。成交、裁决、采纳还是要回对应页面记，这里不写库。', 'ok',
      { label: '撤下标记', fn: function () { delete state.woDone[gid]; renderView(); } });
    return;
  }
  if (action === 'wo-done-item') {
    const gid = el.dataset.group, iid = el.dataset.item;
    const map = state.woDone[gid] || (state.woDone[gid] = {});
    map[iid] = true;
    renderView();
    toast('这一条今天先放过', '只改本页列表：没有记成交，也没有改规则。明早新数据进来会重新出现。', 'ok',
      { label: '撤下标记', fn: function () { delete map[iid]; renderView(); } });
    return;
  }
  if (action === 'wo-undo-item') {
    const gid = el.dataset.group;
    if (state.woDone[gid]) {
      delete state.woDone[gid][el.dataset.item || '*'];
      if (!Object.keys(state.woDone[gid]).length) delete state.woDone[gid];
    }
    renderView();
    toast('已撤下标记', '这条重新回到「要你处理」。', 'info');
    return;
  }
  if (action === 'wo-clear-done') {
    state.woDone = {};
    renderView();
    toast('已撤下全部标记', '所有分组恢复完整列表。', 'info');
    return;
  }
  if (el.dataset.jobRerun) {
    const job = WO_JOBS.filter(function (x) { return x.id === el.dataset.jobRerun; })[0];
    if (job) woRerunJob(job);
    return;
  }
  if (el.dataset.taskRetry) {
    const t2 = woTaskById(el.dataset.taskRetry);
    if (t2) woTaskRetry(t2);
    woEnsureTicker();
    return;
  }
  if (el.dataset.taskCancel) {
    const t3 = woTaskById(el.dataset.taskCancel);
    if (t3) woTaskCancel(t3);
    return;
  }

  if (action === 'task-center') { openDrawer('tasks'); return; }
  if (action === 'open-palette') { openPalette(); return; }
  if (action === 'select-rule') { selectRule(id); return; }
  if (action === 'select-cand') { selectCand(el.dataset.cand); return; }
  if (action === 'cand-tab') { state.candTab = el.dataset.tab; const c = CANDIDATE_POOL.find((x) => x.stock_code === state.candId); const detail = $('#cand-detail'); if (detail && c) { detail.innerHTML = candDetailHtml(c); hydrateIcons(detail); } return; }
  if (action === 'cand-gen') {
    const c = CANDIDATE_POOL.find((x) => x.stock_code === el.dataset.cand);
    state.plGen = el.dataset.cand; state.plCode = ''; state.plDate = ''; state.plNewOpen = true;
    location.hash = '#/plans?gen=' + el.dataset.cand;
    toast('已带到建仓计划页', '「' + (c ? c.stock_name : el.dataset.cand) + '」填进新建表单了，点生成才会跑判级和量化重算。', 'ok');
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
  if (action.indexOf('pl-') === 0) { handlePlansAction(action, el); return; }
  if (action.indexOf('mi-') === 0) { handleMarketIntelAction(action, el); return; }
  if (action.indexOf('pp-') === 0) { handlePaperAction(action, el); return; }
  if (action.indexOf('hd-') === 0) { handleHdAction(action, el); return; }
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

/* 持仓就地表单：输入先落到 state.hdForm.draft，这样上下键换行、重渲染都不会吞掉已经敲进去的数字 */
function hdTradeCapture(e) {
  const el = e.target, d = el.dataset && state.hdTradeDrafts[el.dataset.hd];
  if (!d) return;
  if (el.hasAttribute('data-trade-duplicates')) { d.duplicatesOk = el.checked; return; }
  if (d.preview) return;
  if (el.hasAttribute('data-trade-reason')) d.reason = el.value;
  else if (el.hasAttribute('data-trade-paste')) d.paste = el.value;
  else if (el.dataset.field) {
    const t = d.entries.find(t => t.id === el.dataset.trade);
    if (t && d.editing.includes(t.id)) t[el.dataset.field] = el.value;
  }
  d.discardAsk = false; d.duplicatesOk = false;
}
document.addEventListener('input', hdTradeCapture);
document.addEventListener('change', hdTradeCapture);
document.addEventListener('paste', e => {
  const el = e.target;
  if (!el.dataset || el.dataset.field !== 'date') return;
  const text = e.clipboardData.getData('text/plain');
  if (!text.includes('\t')) return;
  const r = hdTradeStock(el.dataset.hd);
  if (!r || hdTradeLedger(r).entries.some(t => t.id === el.dataset.trade)) return;
  e.preventDefault(); hdTradePaste(r, text, el.dataset.trade); renderView();
});
document.addEventListener('keydown', e => {
  const el = e.target;
  if (e.key !== 'Tab' || e.shiftKey || !el.dataset || el.dataset.field !== 'note') return;
  const r = hdTradeStock(el.dataset.hd), d = r && state.hdTradeDrafts[r.id];
  if (!d || d.entries[d.entries.length - 1].id !== el.dataset.trade) return;
  e.preventDefault(); hdTradeAdd(r); renderView();
  const inputs = document.querySelectorAll('.hd-trade-table [data-field="date"]');
  inputs[inputs.length - 1].focus({ preventScroll: true });
});
document.addEventListener('input', (e) => {
  const t = e.target;
  if (!state.hdForm || !t || !t.id || t.id.indexOf('hd-f-') !== 0) return;
  const key = t.id.replace('hd-f-', '');
  state.hdForm.draft = state.hdForm.draft || {};
  state.hdForm.draft[key] = t.value;
});

document.addEventListener('input', (e) => {
  const t = e.target;
  if (!state.ppForm || !t || !t.id) return;
  if (t.id === 'pp-rv-reason' || t.id === 'pp-a-reason') state.ppForm.reason = t.value;
});
document.addEventListener('change', (e) => {
  const t = e.target;
  if (state.ppForm && t && t.name === 'pp-rv-verdict') state.ppForm.verdict = t.value;
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
  if (state.route === '#/paper' && state.ppTab === 'positions' && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    if (e.target instanceof Element && e.target.matches('input, textarea, select')) return;
    const list = ppValuation(ppAcc()).rows;
    if (!list.length) return;
    e.preventDefault();
    const idx = list.findIndex((r) => r.code === state.ppPos);
    const step = e.key === 'ArrowDown' ? 1 : -1;
    const next = list[Math.max(0, Math.min(list.length - 1, (idx < 0 ? 0 : idx + step)))];
    state.ppPos = next.code;
    renderView();
    syncPaperHash();
    const rowEl = $('.pp-row[data-code="' + next.code + '"]');
    if (rowEl) rowEl.scrollIntoView({ block: 'nearest' });
    return;
  }
  if (state.route === '#/holdings' && state.hdView !== 'exited' && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    if (e.target instanceof Element && e.target.matches('input, textarea, select')) return;
    const list = hdVisible();
    if (!list.length) return;
    e.preventDefault();
    const idx = list.findIndex((r) => String(r.id) === String(state.hdId));
    const step = e.key === 'ArrowDown' ? 1 : -1;
    const next = list[Math.max(0, Math.min(list.length - 1, (idx < 0 ? 0 : idx + step)))];
    state.hdId = Number(next.id);
    renderView();
    syncHdHash();
    const rowEl = $('.hd-row[data-hd="' + next.id + '"]');
    if (rowEl) rowEl.scrollIntoView({ block: 'nearest' });
    return;
  }
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('.rule-row[role="button"], .hd-row[role="button"]')) {
    e.preventDefault();
    if (e.target.dataset.hd) {
      const row = hdById(e.target.dataset.hd);
      if (row) hdOpenForm(row.id, hdEnterKind(row));
      return;
    }
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
