const app = getApp();

Page({
  data: { userInfo: null, points: 0, premium: {}, premiumMsg: '', payPlans: [], selectedPlan: 'pro_monthly', payLoading: false },
  onShow() {
    this.setData({ userInfo: app.globalData.userInfo });
    this.loadPoints(); this.loadPremium(); this.loadPayPlans();
  },
  async loadPoints() {
    try { const data = await app.get('/api/v1/tasks/points/summary'); this.setData({ points: data.total_points }); } catch {}
  },
  async loadPremium() {
    try { const data = await app.get('/api/v1/premium/status'); this.setData({ premium: data }); } catch {}
  },
  async loadPayPlans() {
    try { const data = await app.get('/api/v1/payment/plans'); this.setData({ payPlans: data.plans || [] }); } catch {}
  },
  selectPlan(e) { this.setData({ selectedPlan: e.currentTarget.dataset.id }); },
  async createOrder() {
    this.setData({ payLoading: true });
    try {
      const order = await app.post('/api/v1/payment/orders', { plan_id: this.data.selectedPlan, method: 'wechat' });
      try {
        wx.requestPayment({
          timeStamp: order.payment_params.timeStamp,
          nonceStr: order.payment_params.nonceStr,
          package: order.payment_params.package,
          signType: order.payment_params.signType,
          paySign: order.payment_params.paySign,
          success: async () => {
            await app.post('/api/v1/payment/orders/' + order.order_id + '/pay', { transaction_id: 'WX' + Date.now() });
            wx.showToast({ title: '支付成功！', icon: 'success' }); this.loadPremium();
          },
          fail: () => { wx.showToast({ title: '支付取消', icon: 'none' }); },
        });
      } catch (e) {
        // Dev mode: simulate payment
        await app.post('/api/v1/payment/orders/' + order.order_id + '/pay', { transaction_id: 'SIM' + Date.now() });
        wx.showToast({ title: '支付成功(模拟)', icon: 'success' }); this.loadPremium();
      }
    } catch { wx.showToast({ title: '创建订单失败', icon: 'error' }); }
    this.setData({ payLoading: false });
  },
  goVip() { wx.navigateTo({ url: '/pages/vip/vip' }); },
  goGame() { wx.navigateTo({ url: '/pages/game/game' }); },
  goStore() { wx.navigateTo({ url: '/pages/store/store' }); },
  goCommunity() { wx.navigateTo({ url: '/pages/community/community' }); },
  goKnowledge() { wx.navigateTo({ url: '/pages/knowledge/knowledge' }); },
  goBadges() {},
  logout() { app.logout(); wx.reLaunch({ url: '/pages/login/login' }); },
});
