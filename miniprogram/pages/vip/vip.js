const app = getApp();

const tierFeatures = {
  free: ['基础睡眠记录', 'AI助手(每日5次)', '白噪音基础', '每日任务'],
  freeMissing: ['深度睡眠报告', '睡眠预测', '高级白噪音', '语音日记', '家庭共享'],
  pro: ['无限AI对话', '高级白噪音引擎', '深度睡眠报告', '睡眠预测', '优先支持', '全部改善计划'],
  premium: ['全部Pro功能', 'AI深度分析报告', '个性化睡眠教练', '语音日记', '高级睡眠故事', '健康数据同步', '家庭共享(5人)']
};

const vipCompareRows = [
  { name: '每日AI对话', free: '5次', pro: '无限', premium: '无限', highlight: true },
  { name: '白噪音引擎', free: '基础', pro: '高级', premium: '全部', highlight: false },
  { name: '睡眠报告', free: '基础', pro: '深度', premium: 'AI深度', highlight: true },
  { name: '睡眠预测', free: '✗', pro: '✓', premium: '✓', highlight: false },
  { name: '语音日记', free: '✗', pro: '✗', premium: '✓', highlight: false },
  { name: '睡眠故事', free: '3个', pro: '全部', premium: '全部+定制', highlight: false },
  { name: '改善计划', free: '基础', pro: '全部', premium: 'AI定制', highlight: true },
  { name: '健康数据同步', free: '✗', pro: '✗', premium: '✓', highlight: false },
  { name: '家庭共享', free: '✗', pro: '✗', premium: '5人', highlight: false },
  { name: '优先客服', free: '✗', pro: '✓', premium: '✓', highlight: false },
  { name: '商城折扣', free: '无', pro: '95折', premium: '9折', highlight: false }
];

const vipPerks = [
  { icon: '🎁', title: '专属折扣', desc: '助眠商城9折优惠' },
  { icon: '🚀', title: '优先体验', desc: '新功能抢先试用' },
  { icon: '💎', title: '专属标识', desc: '尊贵会员身份' },
  { icon: '🎫', title: '会员活动', desc: '定期线上讲座' }
];

Page({
  data: {
    premium: {},
    vipBilling: 'monthly',
    payMethod: 'wechat',
    payOrder: null,
    payOrders: [],
    payLoading: false,
    referralCode: '',
    referralCount: 0,
    referralReward: 0,
    vipDaysLeft: 0,
    tierFeatures: tierFeatures,
    vipCompareRows: vipCompareRows,
    vipPerks: vipPerks
  },

  onShow() {
    this.loadPremium();
    this.loadPayOrders();
  },

  async loadPremium() {
    try {
      const data = await app.get('/api/v1/premium/status');
      const days = this.calcVipDays(data);
      this.setData({ premium: data, vipDaysLeft: days });
    } catch {}
  },

  async loadPayOrders() {
    try {
      const data = await app.get('/api/v1/payment/orders');
      this.setData({ payOrders: data.orders || [] });
    } catch {}
  },

  async loadReferral() {
    try {
      const data = await app.get('/api/v1/referral/code');
      this.setData({
        referralCode: data.code,
        referralCount: data.invite_count || 0,
        referralReward: data.reward_yuan || 0
      });
      wx.showToast({ title: '已刷新', icon: 'success' });
    } catch {
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  calcVipDays(premium) {
    if (premium.tier !== 'free' && premium.expires_at) {
      const diff = new Date(premium.expires_at) - new Date();
      return Math.max(0, Math.ceil(diff / 86400000));
    }
    return 0;
  },

  setBilling(e) {
    this.setData({ vipBilling: e.currentTarget.dataset.type });
  },

  async createPayOrder(e) {
    const plan = e.currentTarget.dataset.plan;
    this.setData({ payLoading: true });
    try {
      const data = await app.post('/api/v1/payment/orders', { plan_id: plan, method: 'wechat' });
      this.setData({ payOrder: data, payLoading: false });
    } catch {
      wx.showToast({ title: '创建订单失败', icon: 'error' });
      this.setData({ payLoading: false });
    }
  },

  async confirmPay() {
    this.setData({ payLoading: true });
    try {
      const order = this.data.payOrder;
      await app.post('/api/v1/payment/orders/' + order.order_id + '/pay', { transaction_id: 'SIM' + Date.now() });
      wx.showToast({ title: '支付成功！', icon: 'success' });
      this.setData({ payOrder: null, payLoading: false });
      this.loadPremium();
      this.loadPayOrders();
    } catch {
      wx.showToast({ title: '支付失败', icon: 'error' });
      this.setData({ payLoading: false });
    }
  },

  closePayModal() {
    this.setData({ payOrder: null });
  },

  setPayMethod(e) {
    this.setData({ payMethod: e.currentTarget.dataset.method });
  }
});
