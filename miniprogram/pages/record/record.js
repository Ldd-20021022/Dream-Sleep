const app = getApp();
function pad(n) { return String(n).padStart(2, '0'); }

Page({
  data: {
    mode: 'timer',  // timer | form
    diaryDate: '',
    // Timer mode
    timerState: 'idle', sleepStart: null, sleepStartDisplay: '',
    sleepElapsed: '00:00:00', sleepQuality: 3, sleepQualityStars: '⭐⭐⭐',
    sleepTags: [], sleepNotes: '', quickFeel: '', quickStatus: '', submitting: false,
    // Form mode
    bedHour: 22, bedMin: 0, wakeHour: 6, wakeMin: 30,
    quality: 3, qualityStars: '⭐⭐⭐', tags: [], notes: '',
    voiceText: '', voiceLoading: false,
    // Pre-computed
    tagList: [], bedHours: [], bedMins: [], formError: '',
    // Share
    shareCard: null,
    showShareModal: false,
    // First record celebration
    showFirstModal: false,
    firstRecord: null,
    // History
    records: [],
  },
  _timer: null,

  onHide() {
    // 暂停计时器但保留状态，切回时恢复
    if (this._timer) {
      app.globalData._sleepTimer = {
        state: this.data.timerState,
        start: this.data.sleepStart,
        elapsed: this.data.sleepElapsed,
      };
      clearInterval(this._timer);
      this._timer = null;
    }
  },
  onShow() {
    var d = new Date();
    var hours = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23];
    var mins = [0,5,10,15,20,25,30,35,40,45,50,55];
    var tagNames = ['做梦','失眠','早醒','夜醒','深睡','浅睡','午休','熬夜'];
    var tagList = tagNames.map(function (n) { return { name: n, on: false }; });
    this.setData({
      diaryDate: d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate()),
      bedHours: hours, bedMins: mins, tagList: tagList, formError: ''
    });
    // 恢复计时器
    if (this.data.timerState === 'sleeping') {
      this._startTicking();
    } else if (app.globalData._sleepTimer && app.globalData._sleepTimer.state === 'sleeping') {
      this.setData({
        timerState: 'sleeping',
        sleepStart: app.globalData._sleepTimer.start,
        sleepStartDisplay: this.formatTimeStr(app.globalData._sleepTimer.start),
      });
      this._startTicking();
      delete app.globalData._sleepTimer;
    }
    this.checkExistingTimer();
    this.loadRecords();
  },
  onUnload() {
    if (this._timer) {
      // 存到全局，下次回来可以恢复
      app.globalData._sleepTimer = {
        state: this.data.timerState,
        start: this.data.sleepStart,
      };
      clearInterval(this._timer);
      this._timer = null;
    }
  },

  // Check if there's an ongoing sleep session from a previous app launch
  checkExistingTimer() {
    const saved = wx.getStorageSync('sleep_timer');
    if (saved && saved.state === 'sleeping') {
      this.setData({
        timerState: 'sleeping',
        sleepStart: saved.start,
        sleepStartDisplay: this.formatTimeStr(saved.start),
      });
      this._startTicking();
    }
  },

  // ===== Timer Mode =====
  switchMode(e) { this.setData({ mode: e.currentTarget.dataset.mode }); },

  startSleep() {
    const now = new Date();
    const start = now.toISOString();
    const display = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
    wx.setStorageSync('sleep_timer', { state: 'sleeping', start });
    this.setData({
      timerState: 'sleeping',
      sleepStart: start,
      sleepStartDisplay: display,
      sleepElapsed: '00:00:00',
      diaryDate: `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`,
    });
    this._startTicking();
    wx.showToast({ title: '💤 晚安，好梦', icon: 'none' });
  },

  _startTicking() {
    if (this._timer) clearInterval(this._timer);
    this._timer = setInterval(() => {
      if (!this.data.sleepStart) return;
      const elapsed = Math.floor((Date.now() - new Date(this.data.sleepStart).getTime()) / 1000);
      const h = Math.floor(elapsed / 3600);
      const m = Math.floor((elapsed % 3600) / 60);
      const s = elapsed % 60;
      this.setData({ sleepElapsed: `${pad(h)}:${pad(m)}:${pad(s)}` });
    }, 1000);
  },

  wakeUp() {
    if (this._timer) clearInterval(this._timer);
    const now = new Date();
    const elapsed = Math.floor((now - new Date(this.data.sleepStart)) / 1000);
    const h = Math.floor(elapsed / 3600);
    const m = Math.floor((elapsed % 3600) / 60);
    this.setData({
      timerState: 'woke',
      sleepElapsed: `${pad(h)}:${pad(m)}:00`,
      sleepQuality: 3,
      sleepQualityStars: '⭐⭐⭐',
    });
  },

  cancelSleep() {
    if (this._timer) clearInterval(this._timer);
    wx.removeStorageSync('sleep_timer');
    this.setData({ timerState: 'idle', sleepStart: null, sleepElapsed: '00:00:00' });
  },

  // Quality in timer mode
  onSleepQualityChange(e) {
    const v = parseInt(e.detail.value);
    this.setData({ sleepQuality: v, sleepQualityStars: '⭐'.repeat(v) });
  },

  // Quick feel selectors — auto-fill quality + tags
  setQuickFeel(e) {
    const feel = e.currentTarget.dataset.feel;
    const mapping = {
      great: { quality: 5, tags: ['深睡'] },
      ok: { quality: 4, tags: ['深睡'] },
      tired: { quality: 2, tags: ['浅睡'] },
      bad: { quality: 1, tags: ['失眠', '浅睡'] },
    };
    const m = mapping[feel] || { quality: 3, tags: [] };
    this.setData({
      quickFeel: feel,
      sleepQuality: m.quality,
      sleepQualityStars: '⭐'.repeat(m.quality),
      sleepTags: m.tags,
      quickStatus: '',
    });
  },
  setQuickStatus(e) {
    const status = e.currentTarget.dataset.status;
    const statusTags = {
      fast_sleep: [],
      toss: ['失眠'],
      wake_up: ['夜醒'],
      dream: ['做梦'],
    };
    const extraTags = statusTags[status] || [];
    const merged = [...new Set([...this.data.sleepTags, ...extraTags])];
    this.setData({ quickStatus: status, sleepTags: merged });
  },
  toggleSleepTag(e) {
    const tag = e.currentTarget.dataset.tag;
    let tags = [...this.data.sleepTags];
    const idx = tags.indexOf(tag);
    if (idx >= 0) tags.splice(idx, 1); else tags.push(tag);
    this.setData({ sleepTags: tags });
  },
  onSleepNotesInput(e) { this.setData({ sleepNotes: e.detail.value }); },

  async submitTimerRecord() {
    this.setData({ submitting: true });
    try {
      const start = new Date(this.data.sleepStart);
      const end = new Date();
      const diaryDate = `${start.getFullYear()}-${pad(start.getMonth()+1)}-${pad(start.getDate())}`;
      const bedtime = `${diaryDate}T${pad(start.getHours())}:${pad(start.getMinutes())}:00`;
      const wakeDate = `${end.getFullYear()}-${pad(end.getMonth()+1)}-${pad(end.getDate())}`;
      const waketime = `${wakeDate}T${pad(end.getHours())}:${pad(end.getMinutes())}:00`;

      const result = await app.post('/api/v1/sleep-records', {
        diary_date: diaryDate, bedtime, wake_time: waketime,
        quality: this.data.sleepQuality, tags: this.data.sleepTags, notes: this.data.sleepNotes,
      });

      wx.removeStorageSync('sleep_timer');
      wx.showToast({ title: '✅ 已记录，晚安好梦', icon: 'success' });
      // Dream postcard
      var scenes = ['你梦见了一座漂浮在云端的图书馆', '梦境海里出现了一群发光的鲸鱼', '你沿着一条由星光铺成的小路走到了梦境海深处', '昨晚的梦境里有一只猫说了一句你醒来后怎么也想不起来的话', '梦境海下了一场糖果色的雨每一滴落在地上都变成一朵小花', '一颗流星坠入了你的花园植物们窃窃私语了一整夜'];
      var scene = scenes[Math.floor(Math.random() * scenes.length)];
      app.addPostcard(scene, result.score);
      app.waterGarden();
      app.dailyReset();
      var that = this;
      setTimeout(function () {
        wx.showModal({
          title: '🌌 梦境明信片', content: '「' + scene + '」\n\n深睡 ' + (result.deep_sleep || '--') + ' · REM ' + (result.rem_sleep || '--') + ' · 评分 ' + (result.score || '--'),
          confirmText: '✨ 收藏', cancelText: '关闭',
          success: function (res) {
            if (res.confirm) { app.addFragment(Math.random() > 0.7 ? 'epic' : 'rare'); wx.showToast({ title: '已收藏 + 碎片', icon: 'success' }); }
          }
        });
      }, 500);

      // Prepare share card
      const card = {
        score: result.score, duration: result.duration_hours,
        bedtime: `${pad(start.getHours())}:${pad(start.getMinutes())}`,
        wakeTime: `${pad(end.getHours())}:${pad(end.getMinutes())}`,
        date: diaryDate, feedback: (result.ai_feedback || '').slice(0, 60),
        quality: this.data.sleepQuality,
      };
      var wasFirst = this.data.records.length === 0;
      this.setData({ timerState: 'idle', sleepStart: null, sleepTags: [], sleepNotes: '',
        shareCard: card, showShareModal: !wasFirst,
        showFirstModal: wasFirst, firstRecord: { score: result.score, duration: result.duration_hours },
      });
      if (wasFirst) app.waterGarden();
      this.loadRecords();
    } catch (e) {
      wx.showToast({ title: '网络开了小差，数据还在，稍后再试', icon: 'none' });
    }
    this.setData({ submitting: false });
  },

  // ===== Share Card =====
  closeShareModal() { this.setData({ showShareModal: false }); },
  closeFirstModal() { this.setData({ showFirstModal: false }); },

  async generateShareImage() {
    const card = this.data.shareCard;
    if (!card) return;
    wx.showLoading({ title: '生成卡片中...' });

    const ctx = wx.createCanvasContext('shareCanvas', this);
    const W = 600, H = 800;
    ctx.setFillStyle('#0f0f23'); ctx.fillRect(0, 0, W, H);

    // Gradient border
    const grd = ctx.createLinearGradient(0, 0, W, H);
    grd.addColorStop(0, '#6C63FF'); grd.addColorStop(1, '#0EC9A6');
    ctx.setStrokeStyle(grd); ctx.setLineWidth(4);
    ctx.strokeRect(10, 10, W - 20, H - 20);

    // App name
    ctx.setFillStyle('#888'); ctx.setFontSize(24);
    ctx.setTextAlign('center'); ctx.fillText('梦眠阁 · AI智能睡眠管理', W / 2, 60);

    // Score Ring (simplified)
    ctx.setFillStyle(card.score >= 80 ? '#2ECC71' : card.score >= 60 ? '#3498DB' : card.score >= 40 ? '#F39C12' : '#E74C3C');
    ctx.beginPath(); ctx.arc(W / 2, 200, 80, 0, 2 * Math.PI); ctx.fill();
    ctx.setFillStyle('#fff'); ctx.setFontSize(64); ctx.setFontWeight('bold');
    ctx.setTextAlign('center'); ctx.fillText(String(card.score), W / 2, 210);
    ctx.setFontSize(24); ctx.fillText('分', W / 2, 240);

    // Duration
    ctx.setFillStyle('#fff'); ctx.setFontSize(36);
    ctx.fillText(`${card.duration}h`, W / 2, 320);
    ctx.setFontSize(22); ctx.setFillStyle('#888');
    ctx.fillText(`入睡 ${card.bedtime} · 起床 ${card.wakeTime}`, W / 2, 355);
    ctx.fillText(`日期 ${card.date}`, W / 2, 385);

    // Quality stars
    ctx.setFontSize(40); ctx.fillText('⭐'.repeat(card.quality || 3), W / 2, 440);

    // Feedback
    if (card.feedback) {
      ctx.setFontSize(22); ctx.setFillStyle('#aaa');
      ctx.fillText(`"${card.feedback}"`, W / 2, 500);
    }

    // Tags
    ctx.setFontSize(20); ctx.setFillStyle('#0EC9A6');
    ctx.fillText('来梦眠阁，记录你的每一晚好睡眠 🌙', W / 2, 570);

    // Bottom line
    ctx.setFillStyle('#666'); ctx.setFontSize(18);
    ctx.fillText('扫码体验 · 21天改善你的睡眠', W / 2, 680);

    ctx.draw(false, () => {
      wx.canvasToTempFilePath({
        canvasId: 'shareCanvas', quality: 1,
        success: (res) => {
          wx.hideLoading();
          this.setData({ shareImagePath: res.tempFilePath });
        },
        fail: () => { wx.hideLoading(); wx.showToast({ title: '生成失败', icon: 'none' }); }
      }, this);
    });
  },

  saveShareImage() {
    if (!this.data.shareImagePath) { this.generateShareImage(); return; }
    wx.saveImageToPhotosAlbum({
      filePath: this.data.shareImagePath,
      success: () => wx.showToast({ title: '已保存到相册', icon: 'success' }),
      fail: () => wx.showToast({ title: '请允许保存图片权限', icon: 'none' }),
    });
  },

  // ===== Traditional Form (kept from original) =====
  onDateChange(e) { this.setData({ diaryDate: e.detail.value }); },
  onBedHourChange(e) { this.setData({ bedHour: parseInt(e.detail.value) }); },
  onBedMinChange(e) { this.setData({ bedMin: parseInt(e.detail.value) }); },
  onWakeHourChange(e) { this.setData({ wakeHour: parseInt(e.detail.value) }); },
  onWakeMinChange(e) { this.setData({ wakeMin: parseInt(e.detail.value) }); },
  onQualityChange(e) { const v = parseInt(e.detail.value); this.setData({ quality: v, qualityStars: '⭐'.repeat(v) }); },
  toggleTag(e) {
    var tag = e.currentTarget.dataset.tag;
    var tagList = this.data.tagList.map(function (t) { return { name: t.name, on: t.name === tag ? !t.on : t.on }; });
    var tags = tagList.filter(function (t) { return t.on; }).map(function (t) { return t.name; });
    this.setData({ tagList: tagList, tags: tags });
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
        this.setData({ diaryDate: p.diary_date || this.data.diaryDate, notes: p.notes || this.data.notes, tags: p.tags || [], voiceText: '' });
        wx.showToast({ title: 'AI解析成功: ' + p.summary, icon: 'success' });
      } else { wx.showToast({ title: '已保存语音记录', icon: 'success' }); }
    } catch { wx.showToast({ title: '解析失败', icon: 'error' }); }
    this.setData({ voiceLoading: false });
  },

  async submitFormRecord() {
    if (!this.data.diaryDate) { this.setData({ formError: '请选择日期' }); return; }
    if (this.data.tags.length === 0) { this.setData({ formError: '请至少选择一个睡眠标签' }); return; }
    this.setData({ submitting: true, formError: '' });
    try {
      const bedtime = `${this.data.diaryDate}T${pad(this.data.bedHour)}:${pad(this.data.bedMin)}:00`;
      var isOvernight = this.data.wakeHour < this.data.bedHour ||
        (this.data.wakeHour === this.data.bedHour && this.data.wakeMin <= this.data.bedMin);
      var waketime;
      if (isOvernight) {
        var dt = new Date(this.data.diaryDate); dt.setDate(dt.getDate() + 1);
        waketime = dt.getFullYear() + '-' + pad(dt.getMonth() + 1) + '-' + pad(dt.getDate()) + 'T' + pad(this.data.wakeHour) + ':' + pad(this.data.wakeMin) + ':00';
      } else {
        waketime = this.data.diaryDate + 'T' + pad(this.data.wakeHour) + ':' + pad(this.data.wakeMin) + ':00';
      }

      const result = await app.post('/api/v1/sleep-records', {
        diary_date: this.data.diaryDate, bedtime, wake_time: waketime,
        quality: this.data.quality, tags: this.data.tags, notes: this.data.notes,
      });
      wx.showToast({ title: '✅ 已记录，晚安好梦', icon: 'success' });
      app.waterGarden(); app.dailyReset();

      const card = {
        score: result.score, duration: result.duration_hours,
        bedtime: `${pad(this.data.bedHour)}:${pad(this.data.bedMin)}`,
        wakeTime: `${pad(this.data.wakeHour)}:${pad(this.data.wakeMin)}`,
        date: this.data.diaryDate, feedback: (result.ai_feedback || '').slice(0, 60),
        quality: this.data.quality,
      };
      var wasFirst = this.data.records.length === 0;
      this.setData({ tags: [], notes: '', quality: 3, qualityStars: '⭐⭐⭐',
        shareCard: card, showShareModal: !wasFirst,
        showFirstModal: wasFirst, firstRecord: { score: result.score, duration: result.duration_hours },
      });
      if (wasFirst) app.waterGarden();
      this.loadRecords();
    } catch (e) { wx.showToast({ title: '保存失败', icon: 'none' }); }
    this.setData({ submitting: false });
  },

  formatTimeStr(iso) { if (!iso) return ''; const d = new Date(iso); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; },

  async loadRecords() {
    try {
      const data = await app.get('/api/v1/sleep-records?days=30');
      this.setData({ records: (data && data.records) ? data.records.slice(0, 20) : [] });
    } catch {}
  },

  async deleteRecord(e) {
    const id = e.currentTarget.dataset.id;
    try { await app.del(`/api/v1/sleep-records/${id}`); wx.showToast({ title: '已删除，可以重新记录', icon: 'success' }); this.loadRecords(); } catch {}
  },
});