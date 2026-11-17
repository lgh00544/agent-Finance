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
  '#/overview': {
    title: '工作台总览', desc: '下一批设计：把「今天该做什么」做成行动卡，而不是九张数据卡平铺。',
    scope: ['顶部：今日行动卡（可建仓 / 告警 / 待审）', '中部：市况与持仓摘要，一屏内可读完', '底部：后台任务进度与最近留痕', '与候选池、持仓、告警直接互链']
  },
  '#/candidates': {
    title: '每日候选池', desc: '下一批设计：候选池 → 评分 → 建仓一条线贯通，不再靠 toast 提示。',
    scope: ['候选列表 + 行内评分摘要', '详情抽屉：结论、风险、AI 留痕分 Tab', '选中候选后可直接「去评分」或「生成建仓方案」', '批量验证与历史留痕收进次级面板']
  },
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
  '#/reviews': { title: '交易复盘', desc: '下一批设计：延续黑盒展示规范，建议采纳与留痕清晰可见。', scope: ['主界面只看结论与建议', '算法细节收在专业视图', '建议 → 规则审计 的深链'] },
  '#/experience': { title: '经验沉淀', desc: '下一批设计：经验审核与影响面排序。', scope: ['高影响经验优先', '审核结论与证据', '与规则审计互链'] },
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

/* ---------- 渲染 ---------- */
function renderView() {
  const route = state.route;
  let html = '';
  if (route.startsWith('#/system/')) {
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
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('.rule-row[role="button"]')) {
    e.preventDefault();
    selectRule(e.target.dataset.id);
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
