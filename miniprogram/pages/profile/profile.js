const app = getApp();
Page({
  data: {
    summary: null, loading: true,
    premium: {}, payPlans: [], selectedPlan: 'pro_monthly', payLoading: false,
    heatmap: [], todayMood: '', heatmapWeeks: [],
    showEdit: false, editNickname: '', editAvatar: '',
    showSettings: false, settingTheme: 'dark',
    showPassword: false, oldPwd: '', newPwd: '', pwdLoading: false,
    // Guardian
    guardian: null, attrRows: [], recentFragments: [], recentPostcards: [], recentDiscoveries: [],
    moodList: [{emoji:'😊',name:'愉悦',selected:false},{emoji:'😐',name:'平静',selected:false},{emoji:'😴',name:'困倦',selected:false},{emoji:'😫',name:'疲惫',selected:false},{emoji:'😡',name:'烦躁',selected:false}],
    moodAnimating: false, moodPicked: '', moodMsg: '',
  },
  onShow() { this.loadAll(); this.loadGuardian(); },
  noop() {},

  loadGuardian() {
    var g = app.globalData.guardian;
    if (!g) { this.setData({ guardian: {}, attrRows: [], recentFragments: [], recentPostcards: [], recentDiscoveries: [] }); return; }
    var frags = (g.fragments || []).slice(-8).reverse();
    var cards = (g.postcards || []).slice(0, 6).map(function (pc) {
      return { id: pc.id, date: pc.date, score: pc.score, sceneShort: (pc.scene || '').slice(0, 15) + '...' };
    });
    var disc = (g.discoveries || []).slice(0, 5);
    var colors = { focus: '#3498DB', wisdom: '#9B59B6', resilience: '#E67E22', vitality: '#E74C3C' };
    var names = { focus: '专注力', wisdom: '智慧', resilience: '韧性', vitality: '活力' };
    var icons = { focus: '🧘', wisdom: '📚', resilience: '💪', vitality: '⚡' };
    var keys = ['focus', 'wisdom', 'resilience', 'vitality'];
    var rows = keys.map(function (k) {
      var filled = g[k] || 0;
      var dots = '';
      for (var i = 0; i < 4; i++) dots += i < filled ? '●' : '○';
      return { key: k, icon: icons[k], name: names[k], filled: filled, color: colors[k], dots: dots };
    });
    this.setData({ guardian: g, attrRows: rows, recentFragments: frags, recentPostcards: cards, recentDiscoveries: disc });
  },

  async loadAll() {
    this.setData({ loading: true });
    try {
      const [summary, premium, plans] = await Promise.all([
        app.get('/api/v1/auth/profile-summary').catch(() => null),
        app.get('/api/v1/premium/status').catch(() => ({})),
        app.get('/api/v1/payment/plans').catch(() => ({ plans: [] })),
      ]);
      this.setData({
        summary, premium, payPlans: plans.plans || [],
        loading: false,
      });
      if (summary) app.globalData.userInfo = summary.user;
    } catch { this.setData({ loading: false }); }
    this.loadHeatmap();
  },

  async loadHeatmap() {
    try {
      var d = await app.get('/api/v1/sleep-records/viz/heatmap?days=28');
      var cells = (d.heatmap || []).map(function (h) {
        var score = h.score || 0;
        var emoji = score >= 80 ? '🌟' : score >= 60 ? '☁️' : score > 0 ? '🌧' : '·';
        var dateParts = (h.date || '').split('-');
        var label = dateParts.length === 3 ? dateParts[1] + '/' + dateParts[2] : '';
        return { date: h.date, score: score, emoji: emoji, label: label };
      });
      // Group into weeks
      var weeks = [];
      var week = [];
      cells.forEach(function (c, i) {
        week.push(c);
        if (week.length === 7 || i === cells.length - 1) { weeks.push(week.slice()); week = []; }
      });
      this.setData({ heatmapWeeks: weeks });
    } catch (e) {}
  },

  // ===== Mood Check-in =====
  async setMood(e) {
    var mood = e.currentTarget.dataset.mood;
    var msgs = { '😊': '心情很棒！今晚继续加油 🌙', '😐': '平平淡淡也是真，晚安 💤', '😴': '困了就早点休息吧，别硬撑', '😫': '辛苦了，试试烦恼粉碎机放松一下 💭', '😡': '烦躁的时候深呼吸，一切都会好起来的 🧘' };
    this.setData({ moodAnimating: true, moodPicked: mood, moodMsg: msgs[mood] || '已记录' });
    try { await app.post('/api/v1/auth/quick-mood', { mood: mood }); } catch (e) {}
    var that = this;
    setTimeout(function () { that.setData({ todayMood: mood, moodAnimating: false }); }, 2000);
  },

  // ===== Edit Profile =====
  openEdit() {
    var s = this.data.summary;
    this.setData({
      showEdit: true, editErr: '',
      editNickname: s ? (s.user.nickname || s.user.username) : '',
      editAvatar: s ? (s.user.avatar || '') : '',
    });
  },
  closeEdit() { this.setData({ showEdit: false, editErr: '' }); },
  onNickInput(e) { this.setData({ editNickname: e.detail.value, editErr: '' }); },
  async chooseAvatar() {
    wx.chooseImage({
      count: 1, sizeType: ['compressed'],
      success: (res) => {
        wx.getFileSystemManager().readFile({
          filePath: res.tempFilePaths[0], encoding: 'base64',
          success: (fileRes) => {
            // Store as base64 data URI
            this.setData({ editAvatar: 'data:image/jpeg;base64,' + fileRes.data });
          },
        });
      },
    });
  },
  async saveProfile() {
    if (!this.data.editNickname || this.data.editNickname.length < 2) {
      this.setData({ editErr: '昵称至少2个字符' }); return;
    }
    try {
      await app.put('/api/v1/auth/profile-basic', {
        nickname: this.data.editNickname, avatar: this.data.editAvatar,
      });
      wx.showToast({ title: '已保存', icon: 'success' });
      this.closeEdit(); this.loadAll();
    } catch (e) { wx.showToast({ title: '保存失败', icon: 'none' }); }
  },

  // ===== Premium =====
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
            wx.showToast({ title: '支付成功！', icon: 'success' });
            this.loadAll();
          },
          fail: () => { wx.showToast({ title: '支付取消', icon: 'none' }); },
        });
      } catch (e) {
        await app.post('/api/v1/payment/orders/' + order.order_id + '/pay', { transaction_id: 'SIM' + Date.now() });
        wx.showToast({ title: '支付成功(模拟)', icon: 'success' });
        this.loadAll();
      }
    } catch { wx.showToast({ title: '创建订单失败', icon: 'error' }); }
    this.setData({ payLoading: false });
  },

  // ===== Settings =====
  openSettings() { this.setData({ showSettings: true }); },
  closeSettings() { this.setData({ showSettings: false }); },
  async exportData() {
    try {
      const d = await app.get('/api/v1/sleep-records/export?days=365');
      wx.setClipboardData({ data: d.csv || d.data || JSON.stringify(d), success: () => {
        wx.showToast({ title: '数据已复制到剪贴板', icon: 'success' });
      }});
    } catch { wx.showToast({ title: '导出失败', icon: 'none' }); }
  },
  async deleteAccount() {
    wx.showModal({
      title: '删除账号',
      content: '此操作不可恢复。确定要删除账号和所有数据吗？',
      confirmColor: '#E74C3C',
      success: async (res) => {
        if (res.confirm) {
          wx.showToast({ title: '请联系客服处理', icon: 'none' });
        }
      },
    });
  },

  // ===== Password =====
  openPassword() { this.setData({ showPassword: true, oldPwd: '', newPwd: '' }); },
  closePassword() { this.setData({ showPassword: false }); },
  onOldPwdInput(e) { this.setData({ oldPwd: e.detail.value }); },
  onNewPwdInput(e) { this.setData({ newPwd: e.detail.value }); },
  async changePassword() {
    if (!this.data.oldPwd || !this.data.newPwd) return;
    this.setData({ pwdLoading: true });
    try {
      await app.put('/api/v1/auth/change-password', { old_password: this.data.oldPwd, new_password: this.data.newPwd });
      wx.showToast({ title: '密码已修改', icon: 'success' });
      this.closePassword();
    } catch (e) { wx.showToast({ title: '修改失败，请检查原密码', icon: 'none' }); }
    this.setData({ pwdLoading: false });
  },

  // ===== Notifications =====
  subscribePush() {
    wx.requestSubscribeMessage({
      tmplIds: [app.globalData.wxTemplateId || ''],
      success: async () => {
        wx.login({
          success: async (loginRes) => {
            try { await app.post('/api/v1/auth/wx/subscribe', { code: loginRes.code, openid: loginRes.code || 'wx_user' }); } catch {}
            wx.showToast({ title: '订阅成功！', icon: 'success' });
          },
          fail: () => { wx.showToast({ title: '订阅成功！', icon: 'success' }); }
        });
      },
    });
  },
  unsubscribePush() {
    wx.showModal({
      title: '关闭提醒', content: '关闭后将不再收到睡眠提醒推送。',
      success: async (res) => {
        if (res.confirm) { try { await app.post('/api/v1/auth/wx/unsubscribe', {}); } catch {}; wx.showToast({ title: '已关闭' }); }
      },
    });
  },

  // ===== Navigation =====
  goVip() { wx.navigateTo({ url: '/pages/vip/vip' }); },
  goGame() { wx.navigateTo({ url: '/pages/game/game' }); },
  // goStore() { wx.navigateTo({ url: '/pages/store/store' }); },  // 商城已下线
  goStore() { wx.showToast({ title: '商城即将上线', icon: 'none' }); },
  goCommunity() { wx.navigateTo({ url: '/pages/community/community' }); },
  goKnowledge() { wx.navigateTo({ url: '/pages/courses/courses' }); },
  goBadges() { wx.navigateTo({ url: '/pages/tasks/tasks' }); },
  // 私信/通知页面已移除（轻量化 MVP），功能合并到社区模块
  goMessages() { wx.navigateTo({ url: '/pages/community/community' }); },
  goNotifications() { wx.navigateTo({ url: '/pages/community/community' }); },
  goReport() { wx.navigateTo({ url: '/pages/report/report' }); },
  goOnboarding() { wx.navigateTo({ url: '/pages/onboarding/onboarding' }); },
  goReferral() { wx.navigateTo({ url: '/pages/referral/referral' }); },
  goAnalysis() { wx.switchTab({ url: '/pages/analysis/analysis' }); },
  goTasks() { wx.navigateTo({ url: '/pages/tasks/tasks' }); },
  goCourses() { wx.navigateTo({ url: '/pages/courses/courses' }); },
  logout() { app.logout(); wx.reLaunch({ url: '/pages/login/login' }); },
});
