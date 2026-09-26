import { useEffect, useRef, type ReactNode } from "react";
import { Animated, Easing, type StyleProp, type ViewStyle } from "react-native";

import { useReduceMotion } from "@/hooks/useReduceMotion";

interface MotionRevealProps {
  children: ReactNode;
  delay?: number;
  duration?: number;
  fromY?: number;
  style?: StyleProp<ViewStyle>;
  /** Restart when this key changes (e.g. sport switch / slate id). */
  replayKey?: string | number | boolean;
}

/** Staggered entrance — fade + lift, portfolio-reel style cascade. */
export function MotionReveal({
  children,
  delay = 0,
  duration = 520,
  fromY = 18,
  style,
  replayKey = 0,
}: MotionRevealProps) {
  const reduceMotion = useReduceMotion();
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    progress.setValue(0);
    if (reduceMotion) {
      progress.setValue(1);
      return;
    }
    const anim = Animated.timing(progress, {
      toValue: 1,
      duration,
      delay,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    });
    anim.start();
    return () => anim.stop();
  }, [delay, duration, progress, reduceMotion, replayKey]);

  return (
    <Animated.View
      style={[
        style,
        {
          opacity: progress,
          transform: [
            {
              translateY: progress.interpolate({
                inputRange: [0, 1],
                outputRange: [fromY, 0],
              }),
            },
          ],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}
