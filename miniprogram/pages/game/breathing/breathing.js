const app = getApp();
Page({
  data: {
    phase: 'idle', phaseText: '准备开始', phaseIdx: -1,
    countdown: 0, round: 0, totalRounds: 4,
    circleScale: 1, circleColor: '#6C63FF',
    accuracy: [], score: 0, xpEarned: 0,
    breathingText: '', mode: 'guide', // guide | challenge
  },
  _timer: null, _startTime: 0, _expected: 0,

  onUnload() { clearInterval(this._timer); },

  startBreathing() {
    const mode = this.data.mode;
    const pattern = mode === 'guide' ? [4,7,8] : [4,7,8]; // same pattern
    this.setData({ phase: 'inhale', phaseIdx: 0, round: 1, accuracy: [], score: 0,
      phaseText: '吸气', countdown: 4, circleScale: 1, totalRounds: mode === 'guide' ? 4 : 6 });
    this._animate(4);
  },

  _animate(duration) {
    const startTime = Date.now();
    const startScale = this.data.circleScale === 1 ? 1 : (this.data.phase === 'inhale' ? 1 : 1.6);
    const targetScale = this.data.phase === 'inhale' ? 1.6 : (this.data.phase === 'hold' ? 1.6 : 1);
    const fromColor = this.data.phase === 'inhale' ? '#6C63FF' : (this.data.phase === 'hold' ? '#3498DB' : '#0EC9A6');

    clearInterval(this._timer);
    this._timer = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000;
      const progress = Math.min(elapsed / duration, 1);
      const scale = startScale + (targetScale - startScale) * progress;
      const countdown = Math.ceil(duration - elapsed);

      this.setData({
        circleScale: scale,
        countdown: countdown > 0 ? countdown : 0,
        circleColor: fromColor,
      });

      if (progress >= 1) {
        clearInterval(this._timer);
        this._nextPhase();
      }
    }, 50);
  },

  _nextPhase() {
    const { phase, phaseIdx, round, totalRounds, accuracy } = this.data;
    const phases = ['inhale', 'hold', 'exhale'];
    const phaseNames = {'inhale': '吸气', 'hold': '屏息', 'exhale': '呼气'};
    const durations = {'inhale': 4, 'hold': 7, 'exhale': 8};

    if (this.data.mode === 'challenge' && phase !== 'idle') {
      accuracy.push(1); // simplified: assume good accuracy
      this.setData({ accuracy });
    }

    const nextIdx = phaseIdx + 1;
    if (nextIdx >= 3) {
      // Round complete
      const nextRound = round + 1;
      if (nextRound > totalRounds) {
        this._finishExercise();
        return;
      }
      this.setData({ round: nextRound, phaseIdx: 0, phase: 'inhale', phaseText: '吸气', countdown: 4 });
      this._animate(4);
    } else {
      const newPhase = phases[nextIdx];
      this.setData({ phase: newPhase, phaseIdx: nextIdx, phaseText: phaseNames[newPhase], countdown: durations[newPhase] });
      this._animate(durations[newPhase]);
    }
  },

  async _finishExercise() {
    clearInterval(this._timer);
    const totalScore = Math.round((this.data.accuracy.length / (this.data.totalRounds * 3)) * 100);

    try {
      const data = await app.post('/api/v1/game/breathing/complete', {
        rounds: this.data.totalRounds,
        score: totalScore
      });
      this.setData({
        phase: 'done', phaseText: '完成！',
        score: totalScore, xpEarned: data.xp_awarded || 0,
        level: data.level_name || ''
      });
    } catch {
      this.setData({ phase: 'done', phaseText: '完成！', score: totalScore, xpEarned: totalScore });
    }
  },

  setMode(e) { this.setData({ mode: e.currentTarget.dataset.mode }); },
  reset() { this.setData({ phase: 'idle', phaseText: '准备开始', phaseIdx: -1, countdown: 0, round: 0, circleScale: 1, score: 0, accuracy: [], xpEarned: 0 }); },
});