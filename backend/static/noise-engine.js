/**
 * 梦眠 White Noise Engine — Web Audio API synthesis.
 * 6 natural soundscapes, each with 4 independent audio channels.
 * 13 distinct sound synthesis algorithms.
 * Dynamic evolution + sleep fade mode + Canvas visualizer.
 */
const NoiseEngine = {

  // ── Scene definitions ──
  scenes: {
    forest: {
      name: '森林夜语', icon: '🌲',
      channels: [
        { name: '深棕噪音', type: 'brown_deep', vol: 70 },
        { name: '树叶沙沙', type: 'filtered_rustle', vol: 50 },
        { name: '远鸟鸣叫', type: 'realistic_chirp', vol: 25 },
        { name: '蟋蟀节奏', type: 'rhythmic_pulse', vol: 35 },
      ],
    },
    ocean: {
      name: '海浪轻拍', icon: '🌊',
      channels: [
        { name: '深海低频', type: 'brown_deep', vol: 60 },
        { name: '波浪周期', type: 'cyclic_wave', vol: 65 },
        { name: '远雷滚滚', type: 'distant_thunder', vol: 20 },
        { name: '稀疏气泡', type: 'sparse_bubble', vol: 25 },
      ],
    },
    rain: {
      name: '雨夜窗前', icon: '🌧',
      channels: [
        { name: '连续雨声', type: 'modulated_rain', vol: 75 },
        { name: '水滴节奏', type: 'drip_pattern', vol: 40 },
        { name: '远处雷声', type: 'distant_thunder', vol: 30 },
        { name: '微风轻拂', type: 'gust_cycle', vol: 25 },
      ],
    },
    campfire: {
      name: '篝火星空', icon: '🔥',
      channels: [
        { name: '火焰低鸣', type: 'fire_roar', vol: 65 },
        { name: '噼啪爆裂', type: 'crackle_burst', vol: 45 },
        { name: '微风轻拂', type: 'gust_cycle', vol: 20 },
        { name: '蟋蟀低鸣', type: 'rhythmic_pulse', vol: 30 },
      ],
    },
    wind: {
      name: '山谷微风', icon: '🍃',
      channels: [
        { name: '风涌主频', type: 'gust_cycle', vol: 70 },
        { name: '粉红漂移', type: 'pink_drift', vol: 50 },
        { name: '树叶沙沙', type: 'filtered_rustle', vol: 40 },
        { name: '远鸟鸣叫', type: 'realistic_chirp', vol: 15 },
      ],
    },
    stream: {
      name: '溪流潺潺', icon: '💧',
      channels: [
        { name: '水流主频', type: 'modulated_rain', vol: 60 },
        { name: '水滴叮咚', type: 'drip_pattern', vol: 50 },
        { name: '稀疏气泡', type: 'sparse_bubble', vol: 35 },
        { name: '粉红漂移', type: 'pink_drift', vol: 25 },
      ],
    },
  },

  presets: [
    { name: '深度睡眠', icon: '😴', vols: [80, 30, 0, 0] },
    { name: '减压放松', icon: '🧘', vols: [50, 50, 60, 0] },
    { name: '冥想专注', icon: '🎯', vols: [30, 0, 70, 40] },
    { name: '雨夜入眠', icon: '🌧', vols: [0, 0, 90, 50] },
  ],

  // ── Internal state ──
  _ctx: null,
  _nodes: [],
  _analyser: null,
  _fadeTimer: null,
  _evolveTimer: null,
  _isPlaying: false,
  _masterGain: null,
  _sceneId: null,
  _channels: [],
  _masterVol: 70,
  _timer: 0,
  _startTime: 0,
  _canvasId: null,
  _rafId: null,

  // ── Public API ──
  init(channels, masterVol, sceneId) {
    this._channels = channels;
    this._masterVol = masterVol;
    this._sceneId = sceneId;
  },

  start() {
    if (this._isPlaying) return;
    try {
      this._ctx = new (window.AudioContext || window.webkitAudioContext)();
    } catch (e) {
      console.error('AudioContext failed:', e);
      return false;
    }

    this._masterGain = this._ctx.createGain();
    this._masterGain.gain.value = this._masterVol / 100;
    this._masterGain.connect(this._ctx.destination);

    // Analyser for visualizer
    this._analyser = this._ctx.createAnalyser();
    this._analyser.fftSize = 256;
    this._analyser.connect(this._masterGain);

    this._nodes = [];
    this._channels.forEach((ch, i) => {
      const gain = this._ctx.createGain();
      gain.gain.value = (ch.vol / 100) * (this._masterVol / 100);
      gain.connect(this._analyser);

      const nodes = this._createSound(ch.type, gain);
      this._nodes.push({ ...nodes, gain });
    });

    this._isPlaying = true;
    this._startTime = Date.now();
    this._startEvolution();
    this._startFadeTimer();
    return true;
  },

  stop() {
    this._nodes.forEach(n => {
      try {
        if (n.src) n.src.stop();
        if (n.osc) n.osc.stop();
        if (n.lfo) n.lfo.stop();
      } catch (e) { /* ignore */ }
    });
    this._nodes = [];
    if (this._ctx) {
      this._ctx.close();
      this._ctx = null;
    }
    this._isPlaying = false;
    this._clearTimers();
    this._stopVisualizer();
  },

  setChannelVol(i, v) {
    this._channels[i].vol = v;
    if (this._nodes[i]) {
      this._nodes[i].gain.gain.value = (v / 100) * (this._masterVol / 100);
    }
  },

  setMasterVol(v) {
    this._masterVol = v;
    if (this._isPlaying && this._nodes.length > 0) {
      this._channels.forEach((ch, i) => {
        if (this._nodes[i]) {
          this._nodes[i].gain.gain.value = (ch.vol / 100) * (v / 100);
        }
      });
    }
  },

  isPlaying() { return this._isPlaying; },

  // ── Sound Synthesis ──
  _createSound(type, gainNode) {
    const ctx = this._ctx;
    const sr = ctx.sampleRate;

    switch (type) {
      case 'brown_deep': return this._makeBrownNoise(gainNode);
      case 'pink_drift': return this._makePinkNoise(gainNode);
      case 'filtered_rustle': return this._makeFilteredNoise(gainNode, 2000, 4000);
      case 'realistic_chirp': return this._makeChirps(gainNode);
      case 'rhythmic_pulse': return this._makeRhythmicPulse(gainNode, 4.5);
      case 'cyclic_wave': return this._makeCyclicWave(gainNode);
      case 'distant_thunder': return this._makeThunder(gainNode);
      case 'drip_pattern': return this._makeDrips(gainNode);
      case 'modulated_rain': return this._makeModulatedNoise(gainNode, 0.5);
      case 'gust_cycle': return this._makeGustCycle(gainNode);
      case 'fire_roar': return this._makeFilteredNoise(gainNode, 80, 300);
      case 'crackle_burst': return this._makeCrackle(gainNode);
      case 'sparse_bubble': return this._makeBubbles(gainNode);
      default: return this._makePinkNoise(gainNode);
    }
  },

  // Brown noise: -6dB/octave, deep rumble
  _makeBrownNoise(gain) {
    const ctx = this._ctx;
    const bufSize = ctx.sampleRate * 4;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < bufSize; i++) {
      const white = Math.random() * 2 - 1;
      last = (last + 0.02 * white) / 1.02;
      data[i] = last * 3.5;
    }
    const src = ctx.createBufferSource();
    src.buffer = buf; src.loop = true;
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass'; lp.frequency.value = 200; lp.Q.value = 0.5;
    src.connect(lp); lp.connect(gain); src.start();
    return { src, lp };
  },

  // Pink noise: -3dB/octave
  _makePinkNoise(gain) {
    const ctx = this._ctx;
    const bufSize = ctx.sampleRate * 4;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buf.getChannelData(0);
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (let i = 0; i < bufSize; i++) {
      const white = Math.random() * 2 - 1;
      b0 = 0.99886 * b0 + white * 0.0555179;
      b1 = 0.99332 * b1 + white * 0.0750759;
      b2 = 0.96900 * b2 + white * 0.1538520;
      b3 = 0.86650 * b3 + white * 0.3104856;
      b4 = 0.55000 * b4 + white * 0.5329522;
      b5 = -0.7616 * b5 - white * 0.0168980;
      data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11;
      b6 = white * 0.115926;
    }
    const src = ctx.createBufferSource();
    src.buffer = buf; src.loop = true;
    src.connect(gain); src.start();
    return { src };
  },

  // Filtered noise for rustle / fire
  _makeFilteredNoise(gain, lowFreq, highFreq) {
    const ctx = this._ctx;
    const bufSize = ctx.sampleRate * 2;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < bufSize; i++) data[i] = (Math.random() * 2 - 1) * 0.5;
    const src = ctx.createBufferSource();
    src.buffer = buf; src.loop = true;
    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass';
    bp.frequency.value = (lowFreq + highFreq) / 2;
    bp.Q.value = lowFreq / (highFreq - lowFreq);
    src.connect(bp); bp.connect(gain); src.start();
    return { src, bp };
  },

  // Modulated noise for rain
  _makeModulatedNoise(gain, rate) {
    const ctx = this._ctx;
    const bufSize = ctx.sampleRate * 2;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < bufSize; i++) data[i] = (Math.random() * 2 - 1) * 0.3;
    const src = ctx.createBufferSource();
    src.buffer = buf; src.loop = true;
    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass'; bp.frequency.value = 3000; bp.Q.value = 0.8;
    const lfo = ctx.createOscillator();
    lfo.frequency.value = rate; lfo.type = 'sine';
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 800;
    lfo.connect(lfoGain); lfoGain.connect(bp.frequency);
    lfo.start();
    src.connect(bp); bp.connect(gain); src.start();
    return { src, bp, lfo };
  },

  // Bird chirps
  _makeChirps(gain) {
    const ctx = this._ctx;
    const merger = ctx.createGain();
    merger.gain.value = 0.5;
    merger.connect(gain);

    function scheduleChirp() {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(2000 + Math.random() * 2000, now);
      osc.frequency.exponentialRampToValueAtTime(3000 + Math.random() * 2000, now + 0.08);
      osc.frequency.exponentialRampToValueAtTime(1800 + Math.random() * 1000, now + 0.15);
      g.gain.setValueAtTime(0, now);
      g.gain.linearRampToValueAtTime(1, now + 0.02);
      g.gain.linearRampToValueAtTime(0, now + 0.2);
      osc.connect(g); g.connect(merger);
      osc.start(now); osc.stop(now + 0.2);
      setTimeout(scheduleChirp, 2000 + Math.random() * 5000);
    }
    scheduleChirp();
    return { src: null, merger };
  },

  // Cricket rhythm
  _makeRhythmicPulse(gain, rate) {
    const ctx = this._ctx;
    const bufSize = ctx.sampleRate * 2;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < bufSize; i++) data[i] = (Math.random() * 2 - 1) * 0.2;
    const src = ctx.createBufferSource();
    src.buffer = buf; src.loop = true;
    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass'; bp.frequency.value = 4500; bp.Q.value = 6;
    const lfo = ctx.createOscillator();
    lfo.frequency.value = rate; lfo.type = 'square';
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 0.8;
    lfo.connect(lfoGain); lfoGain.connect(gain.gain || gain);
    lfo.start();
    const innerGain = ctx.createGain();
    innerGain.gain.value = 0.4;
    src.connect(bp); bp.connect(innerGain); innerGain.connect(gain);
    src.start();
    return { src, bp, lfo };
  },

  // Ocean waves
  _makeCyclicWave(gain) {
    const ctx = this._ctx;
    const bufSize = ctx.sampleRate * 4;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < bufSize; i++) {
      last = (last + 0.02 * (Math.random() * 2 - 1)) / 1.02;
      data[i] = last * 2;
    }
    const src = ctx.createBufferSource();
    src.buffer = buf; src.loop = true;
    const bp = ctx.createBiquadFilter();
    bp.type = 'lowpass'; bp.frequency.value = 500;
    const lfo = ctx.createOscillator();
    lfo.frequency.value = 0.07; lfo.type = 'sine';
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 0.7;
    lfo.connect(lfoGain);
    const waveGain = ctx.createGain();
    waveGain.gain.value = 0.5;
    lfoGain.connect(waveGain.gain);
    lfo.start();
    src.connect(bp); bp.connect(waveGain); waveGain.connect(gain);
    src.start();
    return { src, bp, lfo, waveGain };
  },

  // Distant thunder
  _makeThunder(gain) {
    const ctx = this._ctx;
    const bufSize = ctx.sampleRate * 6;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < bufSize; i++) {
      last = (last + (Math.random() * 2 - 1) * 0.005) / 1.005;
      data[i] = last * 3;
    }
    // Add thunder rumble events
    for (let e = 0; e < 8; e++) {
      const start = Math.floor(Math.random() * bufSize * 0.9);
      const dur = Math.floor(sr * (1 + Math.random() * 3));
      for (let i = 0; i < dur && start + i < bufSize; i++) {
        data[start + i] += (Math.exp(-i / (sr * 0.5)) * (Math.random() * 2 - 1)) * 0.6;
      }
    }
    const src = ctx.createBufferSource();
    src.buffer = buf; src.loop = true;
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass'; lp.frequency.value = 150;
    src.connect(lp); lp.connect(gain); src.start();
    return { src, lp };
  },

  // Water drips
  _makeDrips(gain) {
    const ctx = this._ctx;
    const merger = ctx.createGain();
    merger.gain.value = 0.6;
    merger.connect(gain);

    function scheduleDrip() {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(800 + Math.random() * 600, now);
      osc.frequency.exponentialRampToValueAtTime(400 + Math.random() * 200, now + 0.3);
      g.gain.setValueAtTime(0, now);
      g.gain.linearRampToValueAtTime(1, now + 0.005);
      g.gain.exponentialRampToValueAtTime(0.01, now + 0.4);
      osc.connect(g); g.connect(merger);
      osc.start(now); osc.stop(now + 0.4);
      setTimeout(scheduleDrip, 500 + Math.random() * 1500);
    }
    scheduleDrip();
    return { src: null, merger };
  },

  // Wind gusts
  _makeGustCycle(gain) {
    const ctx = this._ctx;
    const bufSize = ctx.sampleRate * 3;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < bufSize; i++) {
      last = (last + (Math.random() * 2 - 1) * 0.01) / 1.01;
      data[i] = last * 2;
    }
    const src = ctx.createBufferSource();
    src.buffer = buf; src.loop = true;
    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass'; bp.frequency.value = 600; bp.Q.value = 1.5;
    const lfo = ctx.createOscillator();
    lfo.frequency.value = 0.03 + Math.random() * 0.02; lfo.type = 'sine';
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 0.5;
    lfo.connect(lfoGain); lfoGain.connect(gain.gain || gain);
    lfo.start();
    src.connect(bp); bp.connect(gain); src.start();
    return { src, bp, lfo };
  },

  // Fire crackle
  _makeCrackle(gain) {
    const ctx = this._ctx;
    const merger = ctx.createGain();
    merger.gain.value = 0.5;
    merger.connect(gain);

    function scheduleCrackle() {
      const now = ctx.currentTime;
      const bufSize = Math.floor(ctx.sampleRate * (0.01 + Math.random() * 0.05));
      const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
      const data = buf.getChannelData(0);
      for (let i = 0; i < bufSize; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / bufSize, 3);
      const src = ctx.createBufferSource();
      src.buffer = buf;
      const g = ctx.createGain();
      g.gain.value = 1;
      const bp = ctx.createBiquadFilter();
      bp.type = 'bandpass'; bp.frequency.value = 3000 + Math.random() * 3000; bp.Q.value = 3;
      src.connect(bp); bp.connect(g); g.connect(merger);
      src.start(now);
      setTimeout(scheduleCrackle, 50 + Math.random() * 300);
    }
    scheduleCrackle();
    return { src: null, merger };
  },

  // Sparse bubbles
  _makeBubbles(gain) {
    const ctx = this._ctx;
    const merger = ctx.createGain();
    merger.gain.value = 0.3;
    merger.connect(gain);

    function scheduleBubble() {
      const now = ctx.currentTime;
      const freq = 300 + Math.random() * 500;
      const dur = 0.1 + Math.random() * 0.3;
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, now);
      osc.frequency.exponentialRampToValueAtTime(freq * 0.5, now + dur);
      g.gain.setValueAtTime(0, now);
      g.gain.linearRampToValueAtTime(1, now + 0.01);
      g.gain.exponentialRampToValueAtTime(0.01, now + dur);
      osc.connect(g); g.connect(merger);
      osc.start(now); osc.stop(now + dur + 0.05);
      setTimeout(scheduleBubble, 1000 + Math.random() * 3000);
    }
    scheduleBubble();
    return { src: null, merger };
  },

  // ── Dynamic Evolution ──
  _startEvolution() {
    this._evolveTimer = setInterval(() => {
      if (!this._isPlaying) return;
      this._nodes.forEach((n, i) => {
        try {
          // Vary filter frequency slightly
          if (n.lp && n.lp.frequency) {
            const base = n.lp.frequency.value;
            n.lp.frequency.setTargetAtTime(base * (0.85 + Math.random() * 0.3), this._ctx.currentTime, 2);
          }
          if (n.bp && n.bp.frequency) {
            const base = n.bp.frequency.value;
            n.bp.frequency.setTargetAtTime(base * (0.9 + Math.random() * 0.2), this._ctx.currentTime, 2);
          }
          // Slight volume drift
          if (n.gain && !n.lfo) {
            const ch = this._channels[i];
            if (ch) {
              const baseVol = (ch.vol / 100) * (this._masterVol / 100);
              n.gain.gain.setTargetAtTime(baseVol * (0.9 + Math.random() * 0.2), this._ctx.currentTime, 2);
            }
          }
        } catch (e) { /* ignore */ }
      });
    }, 5000);
  },

  // ── Sleep Fade ──
  _startFadeTimer() {
    if (this._timer <= 0) return;
    const fadeStart = (this._timer - 5) * 60000; // Start fading 5 min before end
    if (fadeStart <= 0) {
      this._fadeTimer = setTimeout(() => this.stop(), this._timer * 60000);
      return;
    }
    // Hold volume, then fade
    this._fadeTimer = setTimeout(() => {
      if (!this._isPlaying || !this._masterGain) return;
      const now = this._ctx.currentTime;
      this._masterGain.gain.setValueAtTime(this._masterVol / 100, now);
      this._masterGain.gain.linearRampToValueAtTime(0, now + 300);
      setTimeout(() => this.stop(), 300000);
    }, fadeStart);
  },

  _clearTimers() {
    if (this._evolveTimer) { clearInterval(this._evolveTimer); this._evolveTimer = null; }
    if (this._fadeTimer) { clearTimeout(this._fadeTimer); this._fadeTimer = null; }
  },

  // ── Canvas Visualizer ──
  startVisualizer(canvasEl) {
    if (!this._analyser) return;
    this._canvasId = canvasEl;
    const ctx2d = canvasEl.getContext('2d');
    const bufLen = this._analyser.frequencyBinCount;
    const data = new Uint8Array(bufLen);

    const draw = () => {
      if (!this._isPlaying) return;
      this._rafId = requestAnimationFrame(draw);
      this._analyser.getByteFrequencyData(data);

      const w = canvasEl.width, h = canvasEl.height;
      ctx2d.fillStyle = 'rgba(15, 15, 26, 0.3)';
      ctx2d.fillRect(0, 0, w, h);

      const barW = (w / bufLen) * 2.5;
      let x = 0;
      for (let i = 0; i < bufLen; i++) {
        const barH = (data[i] / 255) * h * 0.8;
        const grad = ctx2d.createLinearGradient(0, h, 0, h - barH);
        grad.addColorStop(0, '#0ec9a6');
        grad.addColorStop(1, '#6c63ff');
        ctx2d.fillStyle = grad;
        ctx2d.fillRect(x, h - barH, barW, barH);
        x += barW + 1;
      }
    };
    draw();
  },

  _stopVisualizer() {
    if (this._rafId) { cancelAnimationFrame(this._rafId); this._rafId = null; }
  },

  setTimer(minutes) {
    this._timer = minutes;
    this._clearTimers();
    if (this._isPlaying) this._startFadeTimer();
  },
};
