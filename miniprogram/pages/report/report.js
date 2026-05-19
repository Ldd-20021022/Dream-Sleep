const app = getApp();

Page({
  data: {
    report: null,
    stats: null,
    loading: true,
    days: 7,
    exporting: false,
    sharing: false,
  },

  onShow() { this.loadReport(); },

  async loadReport() {
    this.setData({ loading: true });
    try {
      const d = await app.get(`/api/v1/sleep-records/report?days=${this.data.days}`);
      this.setData({
        report: d,
        stats: d.stats || null,
        loading: false,
      });
    } catch {
      this.setData({ loading: false });
    }
  },

  setDays(e) {
    const days = Number(e.currentTarget.dataset.days);
    this.setData({ days });
    this.loadReport();
  },

  async exportCSV() {
    if (this.data.exporting) return;
    this.setData({ exporting: true });
    try {
      const d = await app.get(`/api/v1/sleep-records/export?days=${this.data.days}`);
      // Download CSV as text file
      wx.setClipboardData({
        data: d.csv || d.data || JSON.stringify(d),
        success: () => {
          wx.showToast({ title: 'CSV已复制到剪贴板', icon: 'success' });
        },
      });
    } catch {
      wx.showToast({ title: '导出失败', icon: 'none' });
    }
    this.setData({ exporting: false });
  },

  async shareReport() {
    this.setData({ sharing: true });
    wx.showToast({ title: '可截图分享给朋友', icon: 'none' });
    this.setData({ sharing: false });
  },

  goAnalysis() {
    wx.navigateTo({ url: '/pages/analysis/analysis' });
  },
});
