const app = getApp();

function pad(n) { return String(n).padStart(2, '0'); }

Page({
  data: {
    diaryDate: '',
    bedHour: 22, bedMin: 0,
    wakeHour: 6, wakeMin: 30,
    quality: 3,
    qualityStars: '⭐⭐⭐',
    tags: [],
    notes: '',
    voiceText: '',
    voiceLoading: false,
    submitting: false,
    records: [],
  },

  onShow() {
    const d = new Date();
    this.setData({ diaryDate: `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}` });
    this.loadRecords();
  },

  // Date
  onDateChange(e) { this.setData({ diaryDate: e.detail.value }); },

  // Bedtime
  onBedHourChange(e) { this.setData({ bedHour: parseInt(e.detail.value) }); },
  onBedMinChange(e) { this.setData({ bedMin: parseInt(e.detail.value) }); },

  // Wake time
  onWakeHourChange(e) { this.setData({ wakeHour: parseInt(e.detail.value) }); },
  onWakeMinChange(e) { this.setData({ wakeMin: parseInt(e.detail.value) }); },

  // Quality
  onQualityChange(e) {
    const v = parseInt(e.detail.value);
    this.setData({ quality: v, qualityStars: '⭐'.repeat(v) });
  },

  // Tags
  toggleTag(e) {
    const tag = e.currentTarget.dataset.tag;
    let tags = [...this.data.tags];
    const idx = tags.indexOf(tag);
    if (idx >= 0) tags.splice(idx, 1); else tags.push(tag);
    this.setData({ tags });
  },

  onNotesInput(e) { this.setData({ notes: e.detail.value }); },
  onVoiceInput(e) { this.setData({ voiceText: e.detail.value }); },

  async voiceToDiary() {
    if (!this.data.voiceText.trim()) return;
    this.setData({ voiceLoading: true });
    try {
      const data = await app.post('/api/v1/voice/diary', { transcript: this.data.voiceText });
      if (data.parsed) {
        const p = data.parsed;
        this.setData({
          diaryDate: p.diary_date || this.data.diaryDate,
          notes: p.notes || this.data.notes,
          tags: p.tags || [],
          voiceText: '',
        });
        wx.showToast({ title: 'AI解析成功: ' + p.summary, icon: 'success' });
      } else {
        wx.showToast({ title: '已保存语音记录', icon: 'success' });
      }
    } catch { wx.showToast({ title: '解析失败', icon: 'error' }); }
    this.setData({ voiceLoading: false });
  },

  async submitRecord() {
    this.setData({ submitting: true });
    try {
      const bedtime = `${this.data.diaryDate}T${pad(this.data.bedHour)}:${pad(this.data.bedMin)}:00`;
      const waketime = this.data.wakeHour < this.data.bedHour ||
        (this.data.wakeHour === this.data.bedHour && this.data.wakeMin <= this.data.bedMin)
        ? `${this.data.diaryDate}T${pad(this.data.wakeHour)}:${pad(this.data.wakeMin)}:00`
        : (() => { const dt = new Date(this.data.diaryDate); dt.setDate(dt.getDate()+1); return `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}T${pad(this.data.wakeHour)}:${pad(this.data.wakeMin)}:00`; })();

      await app.post('/api/v1/sleep-records', {
        diary_date: this.data.diaryDate,
        bedtime,
        wake_time: waketime,
        quality: this.data.quality,
        tags: this.data.tags,
        notes: this.data.notes,
      });
      wx.showToast({ title: '保存成功', icon: 'success' });
      this.setData({ tags: [], notes: '', quality: 3, qualityStars: '⭐⭐⭐' });
      this.loadRecords();
    } catch (e) {
      wx.showToast({ title: '保存失败: ' + (e.message || ''), icon: 'none' });
    }
    this.setData({ submitting: false });
  },

  async loadRecords() {
    try {
      const data = await app.get('/api/v1/sleep-records?days=30');
      this.setData({ records: (data && data.records) ? data.records.slice(0, 20) : [] });
    } catch {}
  },

  async deleteRecord(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await app.del(`/api/v1/sleep-records/${id}`);
      wx.showToast({ title: '已删除', icon: 'success' });
      this.loadRecords();
    } catch {}
  },
});
