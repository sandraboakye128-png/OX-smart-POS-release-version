// static/js/env.js
// Detects whether we're running inside the Capacitor Android APK
// or as a normal web page, and tracks online/offline state.
//
// Exposes window.OX_ENV. Everything that decides "local DB vs remote API"
// reads OX_ENV.useLocalDb. Nothing else should test the environment directly.

window.OX_ENV = (function () {
  // --- 1. Am I running inside the Capacitor Android wrapper? ---
  const cap = window.Capacitor;

  const isCapacitorNative = !!(
    cap &&
    typeof cap.isNativePlatform === 'function' &&
    cap.isNativePlatform() &&
    typeof cap.getPlatform === 'function' &&
    cap.getPlatform() === 'android'
  );

  // Fallback probes in case Capacitor bridge hasn't injected yet.
  // The APK loads via capacitor:// or file://, and the WebView UA contains
  // the app id. This catches cases where env.js runs before Capacitor boots.
  const looksLikeApk =
    location.protocol === 'capacitor:' ||
    location.protocol === 'file:' ||
    /oxsmart/i.test(navigator.userAgent);

  const runningAsApk = isCapacitorNative || looksLikeApk;

  // --- 2. Online / offline tracking ---
  let online = navigator.onLine;

  function emit() {
    document.dispatchEvent(new CustomEvent('ox:netchange', {
      detail: { online, isApk: runningAsApk }
    }));
  }

  window.addEventListener('online',  () => { online = true;  emit(); });
  window.addEventListener('offline', () => { online = false; emit(); });

  // --- 3. The public surface ---
  return {
    isApk:     runningAsApk,
    isWeb:     !runningAsApk,
    isOnline:  () => online,

    // The single decision point for the whole app.
    // false today on web (no behavior change).
    // true  inside the APK once we start wiring local data.
    useLocalDb: runningAsApk,

    // Lets other modules react to net changes.
    onChange(fn) {
      const handler = (e) => fn(e.detail);
      document.addEventListener('ox:netchange', handler);
      return () => document.removeEventListener('ox:netchange', handler);
    },
  };
})();