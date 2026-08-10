/** 距文档底部多少像素内视为"贴底" */
export const PIN_THRESHOLD = 120;

export interface ScrollMetrics {
  /** 文档总高度 */
  scrollHeight: number;
  /** 已滚动距离 */
  scrollY: number;
  /** 视口高度 */
  viewportHeight: number;
}

/**
 * 判断是否已滚动到接近文档底部。
 *
 * 用于流式输出的"贴底跟随"：贴底时自动跟随新内容，用户主动往上翻阅后
 * 停止跟随，避免把正在阅读的用户强行拽回底部。
 */
export function isNearBottom(
  m: ScrollMetrics,
  threshold: number = PIN_THRESHOLD,
): boolean {
  // 负值出现在 iOS 橡皮筋回弹等过滚动场景，同样应视为贴底
  return distanceFromBottom(m) <= threshold;
}

/** 读取当前窗口的滚动度量 */
export function readWindowScrollMetrics(): ScrollMetrics {
  return {
    scrollHeight: document.documentElement.scrollHeight,
    scrollY: window.scrollY,
    viewportHeight: window.innerHeight,
  };
}

/** 忽略小于该像素数的滚动抖动 */
const SCROLL_JITTER_TOLERANCE = 2;

/** "跳到最新"按钮出现所需的距底距离 */
export const JUMP_SHOW_THRESHOLD = 260;

/** "跳到最新"按钮消失的距底距离 */
export const JUMP_HIDE_THRESHOLD = 100;

/** 距文档底部的像素距离 */
export function distanceFromBottom(m: ScrollMetrics): number {
  return m.scrollHeight - (m.scrollY + m.viewportHeight);
}

/**
 * 判断"跳到最新"按钮是否应显示。
 *
 * 出现与消失使用不同阈值（迟滞 hysteresis）。若共用单一阈值，用户在该阈值
 * 附近轻微滑动就会让按钮反复显隐而闪烁；两个阈值之间形成缓冲带，进入需要
 * 明显滚离底部，退出需要明显靠近底部。
 */
export function resolveJumpButtonVisible(
  distance: number,
  currentlyVisible: boolean,
): boolean {
  return currentlyVisible
    ? distance > JUMP_HIDE_THRESHOLD
    : distance > JUMP_SHOW_THRESHOLD;
}

export interface PinDecisionInput {
  /** 当前是否已接近底部 */
  atBottom: boolean;
  /** 本次滚动前的位置 */
  previousScrollY: number;
  /** 本次滚动后的位置 */
  currentScrollY: number;
  /** 当前的贴底状态 */
  wasPinned: boolean;
}

/**
 * 计算新的"贴底跟随"状态。
 *
 * 只有用户**向上**滚动才解除跟随。这一点很关键：流式输出会不断增高文档，
 * 某些浏览器会因此触发 scroll 事件；若仅凭"当前不在底部"就解除跟随，
 * 内容增长本身就会误判为用户想停止跟随，导致跟随中断。
 */
export function resolvePinState(input: PinDecisionInput): boolean {
  if (input.atBottom) return true;
  const scrolledUp =
    input.currentScrollY < input.previousScrollY - SCROLL_JITTER_TOLERANCE;
  return scrolledUp ? false : input.wasPinned;
}
