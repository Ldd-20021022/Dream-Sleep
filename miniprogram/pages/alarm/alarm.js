const app = getApp();
function pad(n) { return String(n).padStart(2, '0'); }

Page({
  data: {
    alarm: { target_time: '07:00', wake_window: 30, smart_method: 'light', enabled_days: '1,2,3,4,5', is_active: 1 },
    suggestions: [], loading: false, saved: false,
    sleepCycles: [
      { cycles: 4, hours: 6, desc: '6小时 · 4个周期', quality: 'good' },
      { cycles: 5, hours: 7.5, desc: '7.5小时 · 5个周期', quality: 'excellent' },
      { cycles: 6, hours: 9, desc: '9小时 · 6个周期', quality: 'good' },
    ],
    selectedBedtime: '', showBedtimePicker: false,
    bedHour: 22, bedMin: 0,
    dayList: [], alarmError: '',
  },

  buildDayList: function () {
    var names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    var enabled = (this.data.alarm.enabled_days || '').split(',');
    var list = [];
    for (var i = 1; i <= 7; i++) {
      list.push({ day: String(i), name: names[i - 1], enabled: enabled.indexOf(String(i)) > -1 });
    }
    this.setData({ dayList: list });
  },

  onShow() { this.loadAlarm(); },

  async loadAlarm() {
    try {
      var data = await app.get('/api/v1/iot/alarm');
      if (data && data.target_time) {
        this.setData({ alarm: data, saved: true });
      }
    } catch (e) { }
    this.buildDayList();
  },

  async saveAlarm() {
    try {
      await app.post('/api/v1/iot/alarm', this.data.alarm);
      wx.showToast({ title: '闹钟已保存', icon: 'success' });
      this.setData({ saved: true });
    } catch {
      wx.showToast({ title: '保存失败', icon: 'none' });
    }
  },

  setTime(e) { this.setData({ 'alarm.target_time': e.detail.value }); },
  setWindow(e) { this.setData({ 'alarm.wake_window': parseInt(e.detail.value) }); },
  setMethod(e) { this.setData({ 'alarm.smart_method': e.currentTarget.dataset.method }); },
  toggleDay(e) {
    var day = e.currentTarget.dataset.day;
    var days = (this.data.alarm.enabled_days || '1,2,3,4,5').split(',');
    var idx = days.indexOf(day);
    if (idx >= 0) days.splice(idx, 1); else { days.push(day); days.sort(); }
    this.setData({ 'alarm.enabled_days': days.join(',') });
    this.buildDayList();
  },
  toggleActive() { this.setData({ 'alarm.is_active': this.data.alarm.is_active ? 0 : 1 }); },
  async getSmartAlarm() {
    this.setData({ loading: true });
    try {
      const data = await app.get(`/api/v1/sleep-records/smart-alarm?wake_target=${this.data.alarm.target_time}`);
      this.setData({ suggestions: data.suggested_bedtime || [] });
    } catch {}
    this.setData({ loading: false });
  },

  getMethodName(m) {
    return m === 'light' ? '💡 光照唤醒' : m === 'sound' ? '🔔 声音唤醒' : '📳 震动唤醒';
  },
});