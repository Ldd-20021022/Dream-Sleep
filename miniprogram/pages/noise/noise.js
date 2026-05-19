const app = getApp();

Page({
  data: {
    scenes: [
      { id: 'forest', name: '森林夜语', icon: '🌲', desc: '深棕噪音 + 鸟鸣 + 蟋蟀' },
      { id: 'ocean', name: '海浪轻拍', icon: '🌊', desc: '深海低频 + 波浪 + 气泡' },
      { id: 'rain', name: '雨夜窗前', icon: '🌧', desc: '连续雨声 + 水滴 + 远雷' },
      { id: 'campfire', name: '篝火星空', icon: '🔥', desc: '火焰低鸣 + 噼啪爆裂' },
      { id: 'wind', name: '山谷微风', icon: '🍃', desc: '风涌主频 + 粉红漂移' },
      { id: 'stream', name: '溪流潺潺', icon: '💧', desc: '水流主频 + 水滴叮咚' },
    ],
    activeScene: 'forest',
    isPlaying: false,
    masterVol: 70,
    timerMin: 30,
    audioCtx: null,
  },

  stories: [],

  onShow() { this.loadStories(); },
  async loadStories() {
    try { const data = await app.get('/api/v1/voice/stories'); this.setData({ stories: data.stories || [] }); } catch {}
  },
  async playStory(e) {
    const id = e.currentTarget.dataset.id;
    const s = this.data.stories.find(x => x.id === id);
    await app.post(`/api/v1/voice/stories/${id}/play`);
    wx.showToast({ title: '播放: ' + (s ? s.title : ''), icon: 'none' });
  },

  selectScene(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({ activeScene: id });
    if (this.data.isPlaying) {
      this.stopNoise();
      this.startNoise();
    }
  },

  startNoise() {
    const ctx = wx.createInnerAudioContext();
    // WeChat mini-program: use a silent audio loop as background
    // Actual noise synthesis requires Web Audio API which isn't available
    // Use background audio as a workaround
    ctx.src = 'https://mengmian.app/static/silence.mp3'; // placeholder
    ctx.loop = true;
    ctx.volume = this.data.masterVol / 100;
    ctx.play();
    this.setData({ isPlaying: true, audioCtx: ctx });

    if (this.data.timerMin > 0) {
      this._timer = setTimeout(() => this.stopNoise(), this.data.timerMin * 60000);
    }
  },

  stopNoise() {
    if (this.data.audioCtx) {
      this.data.audioCtx.stop();
      this.data.audioCtx.destroy();
    }
    if (this._timer) { clearTimeout(this._timer); this._timer = null; }
    this.setData({ isPlaying: false, audioCtx: null });
  },

  onVolumeChange(e) { this.setData({ masterVol: parseInt(e.detail.value) }); },
  onTimerChange(e) { this.setData({ timerMin: parseInt(e.detail.value) }); },

  onUnload() { this.stopNoise(); },
});
