const app = getApp();

Page({
  data: {
    period: 7,
    stats: null,
    loading: true,
  },

  onShow() { this.loadData(); },

  async loadData() {
    this.setData({ loading: true });
    try {
      const [statsRes, recordsRes] = await Promise.all([
        app.get(`/api/v1/sleep-records/stats/enhanced?days=${this.data.period}`).catch(() => null),
        app.get(`/api/v1/sleep-records?days=${this.data.period}`).catch(() => ({ records: [] })),
      ]);
      this.setData({
        stats: statsRes,
        records: (recordsRes && recordsRes.records) ? recordsRes.records : [],
        loading: false,
      });
    } catch { this.setData({ loading: false }); }
  },

  changePeriod(e) {
    this.setData({ period: parseInt(e.currentTarget.dataset.days) });
    this.loadData();
  },

  getConsistencyLabel(m) {
    if (m == null) return '--';
    return m < 30 ? '规律' : m < 60 ? '一般' : '不规律';
  },
});
