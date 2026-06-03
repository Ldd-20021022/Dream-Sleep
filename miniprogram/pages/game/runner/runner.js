const app = getApp();
Page({
  data: {
    playing: false, gameOver: false,
    score: 0, highScore: 0,
    playerLane: 1, // 0=left, 1=center, 2=right
    obstacles: [], // {lane, top, id}
    energy: 0, combo: 0,
    speed: 1800, // ms per frame
    _timer: null,
  },
  onShow() {
    const hs = wx.getStorageSync('runner_high') || 0;
    this.setData({ highScore: hs });
  },
  onHide() { this._stopGame(); },

  startGame() {
    this.setData({
      playing: true, gameOver: false, score: 0,
      playerLane: 1, obstacles: [], energy: 0, combo: 0, speed: 1800,
    });
    this._spawnObstacle();
    this._gameLoop();
  },

  _gameLoop() {
    if (!this.data.playing) return;
    const obstacles = this.data.obstacles.map(o => ({ ...o, top: o.top + 12 }));
    let score = this.data.score;

    // Check collision
    for (const o of obstacles) {
      if (o.top >= 75 && o.top <= 90 && o.lane === this.data.playerLane) {
        this._endGame();
        return;
      }
      if (o.top > 100) {
        score += 1;
      }
    }

    // Remove off-screen obstacles and spawn new ones
    const active = obstacles.filter(o => o.top < 110);
    if (active.length < 2 && Math.random() < 0.4) {
      this._spawnObstacle();
    }

    // Increase speed over time
    const speed = Math.max(800, 1800 - score * 30);

    this.setData({ obstacles: active, score, speed });

    this.data._timer = setTimeout(() => this._gameLoop(), speed);
  },

  _spawnObstacle() {
    const lane = Math.floor(Math.random() * 3);
    const existing = this.data.obstacles.filter(o => o.top < 30);
    if (existing.some(o => o.lane === lane)) return;
    const obs = [...this.data.obstacles, { lane, top: -10, id: Date.now() }];
    this.setData({ obstacles: obs });
  },

  _endGame() {
    this._stopGame();
    const hs = Math.max(this.data.score, this.data.highScore);
    wx.setStorageSync('runner_high', hs);
    // Submit score
    app.post('/api/v1/game/runner/complete', { score: this.data.score }).catch(() => {});
    this.setData({ playing: false, gameOver: true, highScore: hs });
  },

  _stopGame() {
    if (this.data._timer) { clearTimeout(this.data._timer); this.data._timer = null; }
  },

  moveLeft() {
    if (!this.data.playing) return;
    const newLane = Math.max(0, this.data.playerLane - 1);
    this.setData({ playerLane: newLane });
    wx.vibrateShort({ type: 'light' });
  },

  moveRight() {
    if (!this.data.playing) return;
    const newLane = Math.min(2, this.data.playerLane + 1);
    this.setData({ playerLane: newLane });
    wx.vibrateShort({ type: 'light' });
  },

  restart() { this.startGame(); },
});
