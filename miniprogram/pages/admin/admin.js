const app = getApp();
Page({
  data: { stats: null, reports: [], recentUsers: [], loading: true },
  onShow() { this.loadAll(); },
  async loadAll() {
    this.setData({ loading: true });
    try {
      const [stats, reports, users] = await Promise.all([
        app.get('/api/v1/community/admin/stats'),
        app.get('/api/v1/community/admin/reports'),
        app.get('/api/v1/community/admin/recent-users'),
      ]);
      this.setData({
        stats: stats, reports: reports.reports || [],
        recentUsers: users.users || [], loading: false,
      });
    } catch { this.setData({ loading: false }); }
  },
  async resolveReport(e) {
    const id = e.currentTarget.dataset.id;
    const action = e.currentTarget.dataset.action;
    try {
      await app.put('/api/v1/community/admin/reports/' + id + '/resolve', { action });
      wx.showToast({ title: '已处理' });
      this.loadAll();
    } catch {}
  },
  async deleteUser(e) {
    wx.showToast({ title: '此功能需后端扩展' });
  },
});
