// Web Speech API for Hindi & English Sign Pronunciation

class SpeechService {
  private isEnabled: boolean = true;

  public speak(text: string, lang: 'hi-IN' | 'en-IN' | 'en-US' = 'hi-IN') {
    if (!this.isEnabled || typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return;
    }

    try {
      window.speechSynthesis.cancel(); // Stop any pending speech
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      utterance.rate = 0.95;
      utterance.pitch = 1.05;

      // Select preferred voice if available
      const voices = window.speechSynthesis.getVoices();
      const preferred = voices.find((v) => v.lang.startsWith(lang.slice(0, 2)));
      if (preferred) {
        utterance.voice = preferred;
      }

      window.speechSynthesis.speak(utterance);
    } catch {
      // Speech synthesis unsupported or blocked
    }
  }

  public setEnabled(enabled: boolean) {
    this.isEnabled = enabled;
  }
}

export const speechService = new SpeechService();

