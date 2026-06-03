const app = getApp();
Page({
  data: {
    sounds: [], channels: [],
    masterVol: 70, timerMin: 30, timerActive: false,
    playing: false, presets: [],
    showPresets: false,
  },
  onShow() { this.loadSounds(); },
  async loadSounds() {
    try {
      const d = await app.get('/api/v1/game/soundscape');
      const sounds = (d.sounds || []).map(s => ({
        ...s, vol: 50, active: false, ctx: null,
      }));
      this.setData({ sounds, presets: d.presets || [] });
    } catch {}
  },

  // Toggle individual sound
  toggleSound(e) {
    const id = e.currentTarget.dataset.id;
    const sounds = this.data.sounds.map(s => {
      if (s.id !== id) return s;
      if (s.active) {
        if (s.ctx) { s.ctx.stop(); s.ctx.destroy(); }
        return { ...s, active: false, ctx: null };
      } else {
        const ctx = wx.createInnerAudioContext();
        ctx.src = s.audio_url;
        ctx.loop = true;
        ctx.volume = (s.vol / 100) * (this.data.masterVol / 100);
        ctx.play();
        if (!this._listenStart) this._listenStart = Date.now();
        ctx.onError(() => {
          // Try backup URL
          if (s.backup_url && ctx.src !== s.backup_url) {
            ctx.src = s.backup_url;
            ctx.play();
          }
        });
        return { ...s, active: true, ctx };
      }
    });
    const playing = sounds.some(s => s.active);
    this.setData({ sounds, playing });
  },

  // Volume change per sound
  onSoundVolChange(e) {
    const id = e.currentTarget.dataset.id;
    const vol = parseInt(e.detail.value);
    const sounds = this.data.sounds.map(s => {
      if (s.id !== id) return s;
      if (s.ctx) s.ctx.volume = (vol / 100) * (this.data.masterVol / 100);
      return { ...s, vol };
    });
    this.setData({ sounds });
  },

  // Master volume
  onMasterVolChange(e) {
    const vol = parseInt(e.detail.value);
    this.data.sounds.forEach(s => {
      if (s.ctx) s.ctx.volume = (s.vol / 100) * (vol / 100);
    });
    this.setData({ masterVol: vol });
  },

  // Timer
  onTimerChange(e) { var vals = [15, 30, 60, 90, 0]; this.setData({ timerMin: vals[e.detail.value] || 0 }); },
  toggleTimer() {
    if (this.data.timerActive) {
      if (this._timer) clearTimeout(this._timer);
      this.setData({ timerActive: false });
      return;
    }
    this.setData({ timerActive: true });
    this._timer = setTimeout(() => {
      this.stopAll();
      this.setData({ timerActive: false });
    }, this.data.timerMin * 60000);
  },

  // Stop all
  stopAll() {
    var elapsed = this._listenStart ? Math.floor((Date.now() - this._listenStart) / 60000) : 0;
    if (elapsed >= 25) { app.addFragment(elapsed >= 50 ? 'epic' : 'rare'); }
    this._listenStart = null;
    this.data.sounds.forEach(s => {
      if (s.ctx) { s.ctx.stop(); s.ctx.destroy(); }
    });
    if (this._timer) { clearTimeout(this._timer); this._timer = null; }
    const sounds = this.data.sounds.map(s => ({ ...s, active: false, ctx: null }));
    this.setData({ sounds, playing: false, timerActive: false });
  },

  // Load a preset
  loadPreset(e) {
    const id = e.currentTarget.dataset.id;
    const preset = this.data.presets.find(p => p.id === id);
    if (!preset) return;
    this.stopAll();
    const sounds = this.data.sounds.map(s => {
      const pc = preset.channels.find(c => c.type === s.id);
      if (pc) {
        const ctx = wx.createInnerAudioContext();
        ctx.src = s.audio_url;
        ctx.loop = true;
        ctx.volume = (pc.vol / 100) * (this.data.masterVol / 100);
        ctx.play();
        ctx.onError(() => {
          if (s.backup_url && ctx.src !== s.backup_url) {
            ctx.src = s.backup_url; ctx.play();
          }
        });
        return { ...s, active: true, vol: pc.vol, ctx };
      }
      return s;
    });
    this.setData({ sounds, playing: true, showPresets: false });
  },

  togglePresets() { this.setData({ showPresets: !this.data.showPresets }); },
  onUnload() { this.stopAll(); },
});
