/**
 * Web Crypto API를 사용한 Zero-Knowledge 종단간 암호화(E2EE) 헬퍼
 */

const ITERATIONS = 100000;
const KEY_LEN = 256; // AES-256

// Helper to convert array buffer to base64
function arrayBufferToBase64(buffer: ArrayBuffer | Uint8Array): string {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return typeof window !== 'undefined' ? window.btoa(binary) : Buffer.from(bytes).toString('base64');
}

// Helper to convert base64 to array buffer
function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binaryString = typeof window !== 'undefined' ? window.atob(base64) : Buffer.from(base64, 'base64').toString('binary');
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * 마스터 패스워드와 Salt를 기반으로 AES-GCM 대칭키를 유도합니다.
 */
export async function deriveKey(password: string, salt: Uint8Array): Promise<CryptoKey> {
  if (typeof window === 'undefined') throw new Error('Crypto is only available in browser');

  const enc = new TextEncoder();
  const passwordKey = await window.crypto.subtle.importKey(
    'raw',
    enc.encode(password),
    'PBKDF2',
    false,
    ['deriveKey']
  );

  return window.crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: salt as BufferSource,
      iterations: ITERATIONS,
      hash: 'SHA-256'
    },
    passwordKey,
    {
      name: 'AES-GCM',
      length: KEY_LEN
    },
    false, // exportable
    ['encrypt', 'decrypt']
  );
}

/**
 * 평문을 주어진 패스워드로 암호화하여 "e2ee:Salt(Base64):IV(Base64):Ciphertext(Base64)" 형태로 반환합니다.
 */
export async function encryptText(text: string, password: string): Promise<string> {
  if (typeof window === 'undefined') return text;
  if (!password) return text; // 패스워드가 없으면 일반 저장 폴백

  const enc = new TextEncoder();
  const salt = window.crypto.getRandomValues(new Uint8Array(16));
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  
  const key = await deriveKey(password, salt);
  const encrypted = await window.crypto.subtle.encrypt(
    {
      name: 'AES-GCM',
      iv: iv
    },
    key,
    enc.encode(text)
  );

  const saltB64 = arrayBufferToBase64(salt);
  const ivB64 = arrayBufferToBase64(iv);
  const cipherB64 = arrayBufferToBase64(encrypted);

  return `e2ee:${saltB64}:${ivB64}:${cipherB64}`;
}

/**
 * "e2ee:Salt:IV:Ciphertext" 형태로 암호화된 데이터를 패스워드로 복호화합니다.
 */
export async function decryptText(encryptedText: string, password: string): Promise<string> {
  if (typeof window === 'undefined') return encryptedText;
  if (!password || !encryptedText.startsWith('e2ee:')) return encryptedText;

  try {
    const parts = encryptedText.split(':');
    if (parts.length !== 4) return encryptedText;

    const [, saltB64, ivB64, cipherB64] = parts;
    const salt = new Uint8Array(base64ToArrayBuffer(saltB64));
    const iv = new Uint8Array(base64ToArrayBuffer(ivB64));
    const ciphertext = base64ToArrayBuffer(cipherB64);

    const key = await deriveKey(password, salt);
    const decrypted = await window.crypto.subtle.decrypt(
      {
        name: 'AES-GCM',
        iv: iv
      },
      key,
      ciphertext
    );

    const dec = new TextDecoder();
    return dec.decode(decrypted);
  } catch (error) {
    console.error('Decryption failed:', error);
    return '[복호화 실패: 잘못된 마스터 패스워드]';
  }
}

/**
 * 로컬 스토리지에 E2EE 활성화 상태를 확인하고 잠금을 풀거나 관리하는 헬퍼들
 */
export function isE2eeEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem("mindcare_e2ee_enabled") === "true";
}

export function getSessionPassword(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem("mindcare_master_password");
}

export function setSessionPassword(password: string): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem("mindcare_master_password", password);
}

export function clearSessionPassword(): void {
  if (typeof window === 'undefined') return;
  sessionStorage.removeItem("mindcare_master_password");
}
