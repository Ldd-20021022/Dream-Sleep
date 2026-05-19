const app = getApp();
Page({
  data: { alarm: { target_time: '07:00', wake_window: 30, smart_method: 'light' }, suggestions: [], loading: false },
  onShow() { this.loadAlarm(); },
  async loadAlarm() { try { const data = await app.get('/api/v1/iot/alarm'); this.setData({ alarm: data }); } catch {} },
  async saveAlarm() { try { await app.post('/api/v1/iot/alarm', this.data.alarm); wx.showToast({ title: '已保存' }); } catch {} },
  setField(e) {
    const field = e.currentTarget.dataset.field;
    const v = e.detail.value;
    const alarm = { ...this.data.alarm, [field]: field === 'wake_window' ? parseInt(v) : v };
    this.setData({ alarm });
  },
  setFieldTap(e) {
    const field = e.currentTarget.dataset.field;
    const val = e.currentTarget.dataset.val;
    const alarm = { ...this.data.alarm, [field]: val };
    this.setData({ alarm });
  },
  async getSmartAlarm() {
    this.setData({ loading: true });
    try { const data = await app.get('/api/v1/sleep-records/smart-alarm?wake_target=' + this.data.alarm.target_time); this.setData({ suggestions: data.suggested_bedtime || [] }); } catch {}
    this.setData({ loading: false });
  },
});
