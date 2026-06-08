/**
 * Web Audio API를 활용한 실시간 오프라인 사운드스케이프 합성기
 */

class SoundscapeSynthesizer {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  
  // 빗소리 노드
  private rainSource: AudioBufferSourceNode | null = null;
  private rainGain: GainNode | null = null;
  
  // 싱잉볼 벨 노드
  private bowlInterval: any = null;

  constructor() {}

  private init() {
    if (typeof window === "undefined") return;
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) return;
    
    this.ctx = new AudioContextClass();
    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.setValueAtTime(0.5, this.ctx.currentTime);
    this.masterGain.connect(this.ctx.destination);
  }

  // 1. 빗소리 합성 (Pink Noise 유사 생성 + Lowpass Filter)
  private createRainBuffer(): AudioBuffer {
    if (!this.ctx) throw new Error("AudioContext not initialized");
    const sampleRate = this.ctx.sampleRate;
    const bufferSize = sampleRate * 2; // 2초 루프
    const buffer = this.ctx.createBuffer(1, bufferSize, sampleRate);
    const data = buffer.getChannelData(0);
    
    // Pink noise approximation
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (let i = 0; i < bufferSize; i++) {
      const white = Math.random() * 2 - 1;
      b0 = 0.99886 * b0 + white * 0.0555179;
      b1 = 0.99332 * b1 + white * 0.0750759;
      b2 = 0.96900 * b2 + white * 0.1538520;
      b3 = 0.86650 * b3 + white * 0.3104856;
      b4 = 0.55000 * b4 + white * 0.5329522;
      b5 = -0.7616 * b5 - white * 0.0168980;
      data[i] = b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362;
      data[i] *= 0.11; // 볼륨 정규화
      b6 = white * 0.115926;
    }
    return buffer;
  }

  public startRain(volume: number = 0.3) {
    if (typeof window === "undefined") return;
    if (!this.ctx) this.init();
    if (!this.ctx || !this.masterGain) return;

    if (this.ctx.state === "suspended") {
      this.ctx.resume();
    }

    this.stopRain();

    try {
      const buffer = this.createRainBuffer();
      this.rainSource = this.ctx.createBufferSource();
      this.rainSource.buffer = buffer;
      this.rainSource.loop = true;

      const filter = this.ctx.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.setValueAtTime(600, this.ctx.currentTime); // 고주파 깎아서 먹먹하고 차분하게

      this.rainGain = this.ctx.createGain();
      this.rainGain.gain.setValueAtTime(volume, this.ctx.currentTime);

      this.rainSource.connect(filter);
      filter.connect(this.rainGain);
      this.rainGain.connect(this.masterGain);

      this.rainSource.start(0);
    } catch (e) {
      console.error("Failed to play synthesized rain sound", e);
    }
  }

  public setRainVolume(volume: number) {
    if (this.rainGain && this.ctx) {
      this.rainGain.gain.setValueAtTime(volume, this.ctx.currentTime);
    }
  }

  public stopRain() {
    if (this.rainSource) {
      try {
        this.rainSource.stop();
      } catch (e) {}
      this.rainSource.disconnect();
      this.rainSource = null;
    }
    if (this.rainGain) {
      this.rainGain.disconnect();
      this.rainGain = null;
    }
  }

  // 2. 싱잉볼 (Tibetan Singing Bowl) 주기적 재생 합성
  public playBowlOnce(volume: number = 0.4) {
    if (typeof window === "undefined") return;
    if (!this.ctx) this.init();
    if (!this.ctx || !this.masterGain) return;

    if (this.ctx.state === "suspended") {
      this.ctx.resume();
    }

    const now = this.ctx.currentTime;
    
    const gainNode = this.ctx.createGain();
    gainNode.gain.setValueAtTime(0.001, now);
    // 어택(Attack): 2.5초
    gainNode.gain.linearRampToValueAtTime(volume, now + 2.5);
    // 감쇠(Decay): 11초
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + 13.0);
    gainNode.connect(this.masterGain);

    // 복합 배음 (C#3 마이너 계열 배합 공명 튜닝)
    const freqs = [138.59, 207.89, 277.18, 415.30, 554.37];
    const oscs: OscillatorNode[] = [];

    freqs.forEach((freq, idx) => {
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, now);
      
      const oscGain = this.ctx.createGain();
      const relativeVol = idx === 0 ? 0.35 : (1 / (idx + 1)) * 0.18;
      oscGain.gain.setValueAtTime(relativeVol, now);
      
      osc.connect(oscGain);
      oscGain.connect(gainNode);
      osc.start(now);
      osc.stop(now + 13.5);
      oscs.push(osc);
    });

    setTimeout(() => {
      gainNode.disconnect();
    }, 14000);
  }

  public startBowlLoop(volume: number = 0.4, intervalSeconds: number = 18) {
    this.stopBowlLoop();
    this.playBowlOnce(volume);
    
    this.bowlInterval = setInterval(() => {
      this.playBowlOnce(volume);
    }, intervalSeconds * 1000);
  }

  public stopBowlLoop() {
    if (this.bowlInterval) {
      clearInterval(this.bowlInterval);
      this.bowlInterval = null;
    }
  }

  public stopAll() {
    this.stopRain();
    this.stopBowlLoop();
    if (this.ctx && this.ctx.state !== "closed") {
      try {
        this.ctx.close();
      } catch (e) {}
      this.ctx = null;
      this.masterGain = null;
    }
  }
}

export const soundscape = new SoundscapeSynthesizer();
