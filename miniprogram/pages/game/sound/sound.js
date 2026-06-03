const app = getApp();
Page({
  data: {
    sounds: [], presets: [], channels: {},
    playing: false, playingId: null,
    saved: false, presetName: '我的音景',
  },
  _audioCtx: null,
  _players: {},

  onShow() { this.loadData(); },
  onUnload() { this.stopAll(); },

  async loadData() {
    try { const d = await app.get('/api/v1/game/soundscape'); this.setData({ sounds: d.sounds || [], presets: d.presets || [] }); } catch {}
  },

  setVol(e) {
    const id = e.currentTarget.dataset.id;
    const v = parseInt(e.detail.value);
    this.data.channels[id] = v;
    this.setData({ channels: this.data.channels });
    if (this._players[id]) {
      this._players[id].volume = v / 100;
    }
  },

  loadPreset(e) {
    const p = this.data.presets.find(x => x.id === e.currentTarget.dataset.id);
    if (p) {
      this.setData({ channels: { ...p.channels }, presetName: p.name });
      if (this.data.playing) { this.stopAll(); this.playAll(); }
    }
  },

  togglePlay() {
    if (this.data.playing) {
      this.stopAll();
      this.setData({ playing: false });
    } else {
      this.playAll();
      this.setData({ playing: true });
    }
  },

  playAll() {
    const activeChannels = Object.entries(this.data.channels)
      .filter(([_, vol]) => vol > 0);
    if (activeChannels.length === 0) {
      wx.showToast({ title: '请先调整音量', icon: 'none' });
      this.setData({ playing: false });
      return;
    }
    activeChannels.forEach(([id, vol]) => {
      this._playSound(id, vol);
    });
  },

  _playSound(id, vol) {
    const sound = this.data.sounds.find(s => s.id === id);
    if (!sound || !sound.audio_url) return;

    const audio = wx.createInnerAudioContext();
    audio.src = sound.audio_url;
    audio.loop = true;
    audio.volume = vol / 100;
    audio.play();
    audio.onError((err) => {
      console.log('Audio error:', id, err);
      // Try backup URL if available
      if (sound.backup_url && audio.src !== sound.backup_url) {
        audio.src = sound.backup_url;
        audio.play();
      }
    });
    this._players[id] = audio;
  },

  stopAll() {
    Object.values(this._players).forEach(a => {
      try { a.stop(); a.destroy(); } catch (_) {}
    });
    this._players = {};
  },

  onNameInput(e) { this.setData({ presetName: e.detail.value }); },

  async savePreset() {
    try {
      const d = await app.post('/api/v1/game/soundscape/save', { name: this.data.presetName, channels: this.data.channels });
      wx.showToast({ title: d.message, icon: 'success' });
      this.setData({ saved: true });
    } catch { wx.showToast({ title: '保存失败', icon: 'none' }); }
  },
});