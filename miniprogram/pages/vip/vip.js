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
    payPlans: [], heroPrice: '29', showCompare: false, showOrders: false,
    proMoPrice: '--', proYrPrice: '--', premMoPrice: '--', premYrPrice: '--',
    billingFeedback: false,
    payLoading: false,
    couponCode: '',
    couponApplied: false,
    referralCode: '',
    referralCount: 0,
    referralReward: 0,
    vipDaysLeft: 0,
    orderExpireSeconds: 0,
    tierFeatures: tierFeatures,
    vipCompareRows: vipCompareRows,
    vipPerks: vipPerks
  },

  onShow() {
    this.loadPremium();
    this.loadPayPlans();
    this.loadPayOrders();
  },

  async loadPremium() {
    try {
      const data = await app.get('/api/v1/premium/status');
      const days = this.calcVipDays(data);
      this.setData({ premium: data, vipDaysLeft: days });
    } catch {}
  },

  async loadPayPlans() {
    try {
      var data = await app.get('/api/v1/payment/plans');
      var plans = data.plans || [];
      var findPrice = function (id) { for (var i = 0; i < plans.length; i++) { if (plans[i].id === id) return plans[i].amount_yuan; } return '--'; };
      var findOrig = function (id) { for (var i = 0; i < plans.length; i++) { if (plans[i].id === id) return Math.floor(plans[i].amount / 100); } return '--'; };
      this.setData({
        payPlans: plans,
        heroPrice: findPrice('pro_monthly') !== '--' ? findPrice('pro_monthly') : '29',
        proMoPrice: findPrice('pro_monthly'), proYrPrice: findPrice('pro_yearly'), proYrOrig: findOrig('pro_yearly'),
        premMoPrice: findPrice('premium_monthly'), premYrPrice: findPrice('premium_yearly'), premYrOrig: findOrig('premium_yearly')
      });
    } catch (e) {}
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

  noop: function () {},
  toggleCompare: function () { this.setData({ showCompare: !this.data.showCompare }); },
  toggleOrders: function () { this.setData({ showOrders: !this.data.showOrders }); if (!this.data.showOrders) this.loadPayOrders(); },
  setBilling(e) {
    var type = e.currentTarget.dataset.type;
    this.setData({ vipBilling: type, billingFeedback: true });
    var that = this;
    setTimeout(function () { that.setData({ billingFeedback: false }); }, 300);
  },

  onCouponInput(e) {
    this.setData({ couponCode: e.detail.value.trim() });
  },

  async createPayOrder(e) {
    if (this.data.payLoading) return;
    var plan = e.currentTarget.dataset.plan;
    this.setData({ payLoading: true });
    try {
      const body = { plan_id: plan, method: this.data.payMethod };
      if (this.data.couponCode) body.coupon_code = this.data.couponCode;
      const data = await app.post('/api/v1/payment/orders', body);
      this.setData({
        payOrder: data,
        payLoading: false,
        couponApplied: (data.coupon_discount_yuan || 0) > 0,
        orderExpireSeconds: (data.expire_minutes || 30) * 60
      });
      this.startExpireCountdown();
    } catch (err) {
      wx.showToast({ title: (err && err.detail) || '创建订单失败', icon: 'error' });
      this.setData({ payLoading: false });
    }
  },

  startExpireCountdown() {
    clearInterval(this._expireTimer);
    this._expireTimer = setInterval(() => {
      const sec = this.data.orderExpireSeconds - 1;
      if (sec <= 0) {
        clearInterval(this._expireTimer);
        this.closePayModal();
        wx.showToast({ title: '订单已过期', icon: 'none' });
        return;
      }
      this.setData({ orderExpireSeconds: sec });
    }, 1000);
  },

  async confirmPay() {
    this.setData({ payLoading: true });
    try {
      const order = this.data.payOrder;
      const txnId = 'SIM' + Date.now();
      const result = await app.post('/api/v1/payment/orders/' + order.order_id + '/pay', {
        transaction_id: txnId
      });
      clearInterval(this._expireTimer);
      wx.showToast({ title: '支付成功！', icon: 'success' });
      this.setData({ payOrder: null, payLoading: false, couponCode: '', couponApplied: false });
      this.loadPremium();
      this.loadPayOrders();
    } catch (err) {
      const msg = (err && err.detail) || '支付失败';
      wx.showToast({ title: msg, icon: 'error' });
      this.setData({ payLoading: false });
    }
  },

  async cancelOrder() {
    if (!this.data.payOrder) return;
    try {
      await app.post('/api/v1/payment/orders/' + this.data.payOrder.order_id + '/cancel');
      clearInterval(this._expireTimer);
      wx.showToast({ title: '订单已取消', icon: 'none' });
      this.setData({ payOrder: null, couponCode: '', couponApplied: false });
    } catch {
      wx.showToast({ title: '取消失败', icon: 'error' });
    }
  },

  closePayModal() {
    clearInterval(this._expireTimer);
    this.setData({ payOrder: null, couponCode: '', couponApplied: false });
  },

  setPayMethod(e) {
    this.setData({ payMethod: e.currentTarget.dataset.method });
  },

  getPlanPriceYuan: function (planKey) {
    var plans = this.data.payPlans || [];
    var plan = null;
    for (var i = 0; i < plans.length; i++) { if (plans[i].id === planKey) { plan = plans[i]; break; } }
    return plan ? plan.amount_yuan : '--';
  },

  getPlanOriginalYuan: function (planKey) {
    var plans = this.data.payPlans || [];
    var plan = null;
    for (var i = 0; i < plans.length; i++) { if (plans[i].id === planKey) { plan = plans[i]; break; } }
    return plan ? Math.floor(plan.amount / 100) : '--';
  },
  scrollToPlans: function () {
    wx.pageScrollTo({ selector: '#plans', duration: 300 });
  }
});