const app = getApp();
Page({
  data: {
    garden: null, loading: true,
    waterDrops: 0, sunlight: 0, day: 1,
    plants: [
      { id: 'p1', name: '薰衣草', icon: '🪻', day: 1, unlocked: false, desc: '助眠安神' },
      { id: 'p2', name: '洋甘菊', icon: '🌼', day: 3, unlocked: false, desc: '舒缓焦虑' },
      { id: 'p3', name: '茉莉花', icon: '🌸', day: 5, unlocked: false, desc: '提升睡眠质量' },
      { id: 'p4', name: '月光兰', icon: '🌺', day: 7, unlocked: false, desc: '调节生物钟' },
      { id: 'p5', name: '梦境树', icon: '🌳', day: 14, unlocked: false, desc: '深度睡眠守护' },
    ],
    tasks: [
      { id: 't1', text: '记录今晚睡眠', done: false, reward: '💧+2' },
      { id: 't2', text: '完成2个每日任务', done: false, reward: '☀️+1' },
      { id: 't3', text: '使用白噪音15分钟', done: false, reward: '💧+1' },
      { id: 't4', text: '22:30前上床', done: false, reward: '☀️+2' },
    ],
    showWaterAnim: false, showSunAnim: false,
    showPlantUnlock: false, newPlant: null,
  },
  onShow() { this.loadGarden(); },
  async loadGarden() {
    this.setData({ loading: true });
    try {
      const d = await app.get('/api/v1/game/garden');
      const day = d.day || 1;
      const plants = this.data.plants.map(p => ({ ...p, unlocked: day >= p.day }));
      // Load task status from storage
      const doneTasks = wx.getStorageSync('garden_tasks') || {};
      const tasks = this.data.tasks.map(t => ({ ...t, done: !!doneTasks[t.id] }));
      this.setData({
        garden: d, loading: false,
        waterDrops: d.water || 3,
        sunlight: d.sunlight || 2,
        day, plants, tasks,
      });
    } catch { this.setData({ loading: false }); }
  },

  waterPlant() {
    if (this.data.waterDrops <= 0) { wx.showToast({ title: '水滴不足！完成任务获取', icon: 'none' }); return; }
    this.setData({ showWaterAnim: true, waterDrops: this.data.waterDrops - 1 });
    wx.vibrateShort({ type: 'light' });
    setTimeout(() => this.setData({ showWaterAnim: false }), 800);
    // Check if any plant unlocks today
    const unlocked = this.data.day >= 3 && this.data.waterDrops <= 4;
    if (unlocked && !this.data.plants[1].unlocked) {
      this._unlockPlant(this.data.plants[1]);
    }
  },

  collectSunlight() {
    if (this.data.sunlight <= 0) { wx.showToast({ title: '阳光不足！完成任务获取', icon: 'none' }); return; }
    this.setData({ showSunAnim: true, sunlight: this.data.sunlight - 1 });
    wx.vibrateShort({ type: 'light' });
    setTimeout(() => this.setData({ showSunAnim: false }), 800);
  },

  completeTask(e) {
    const id = e.currentTarget.dataset.id;
    const tasks = this.data.tasks.map(t => {
      if (t.id !== id || t.done) return t;
      // Parse reward
      if (t.reward.includes('💧')) {
        const n = parseInt(t.reward.match(/\d+/)?.[0] || 1);
        this.setData({ waterDrops: this.data.waterDrops + n });
      }
      if (t.reward.includes('☀️')) {
        const n = parseInt(t.reward.match(/\d+/)?.[0] || 1);
        this.setData({ sunlight: this.data.sunlight + n });
      }
      return { ...t, done: true };
    });
    this.setData({ tasks });
    // Save to storage
    const doneTasks = {};
    tasks.filter(t => t.done).forEach(t => { doneTasks[t.id] = true; });
    wx.setStorageSync('garden_tasks', doneTasks);
    wx.showToast({ title: '任务完成！+资源', icon: 'success' });
  },

  _unlockPlant(plant) {
    this.setData({ showPlantUnlock: true, newPlant: plant });
    setTimeout(() => this.setData({ showPlantUnlock: false, newPlant: null }), 2500);
  },

  dismissUnlock() { this.setData({ showPlantUnlock: false, newPlant: null }); },

  getWaterDrops(n) { return Array(Math.min(n, 15)).fill('💧').join(''); },
  getSunIcons(n) { return Array(Math.min(n, 10)).fill('☀️').join(''); },
});
