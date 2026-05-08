import React, { useEffect, useMemo, useState, type ReactElement } from 'react';
import { AnimatePresence, motion } from 'motion/react';

export const AnimatedList = React.memo(
  ({
    className,
    children,
    delay = 50,
  }: {
    className?: string;
    children: React.ReactNode;
    delay?: number;
  }) => {
    const [index, setIndex] = useState(0);
    const childrenArray = React.Children.toArray(children);

    useEffect(() => {
      setIndex(0);
    }, [childrenArray.length]);

    useEffect(() => {
      if (index < childrenArray.length - 1) {
        const timeout = setTimeout(() => {
          setIndex((prevIndex) => prevIndex + 1);
        }, delay);
        return () => clearTimeout(timeout);
      }

      return undefined;
    }, [index, childrenArray.length, delay]);

    const itemsToShow = useMemo(
      () => childrenArray.slice(0, index + 1),
      [index, childrenArray],
    );

    return (
      <div className={className}>
        <AnimatePresence mode="popLayout">
          {itemsToShow.map((item) => {
            const key = (item as ReactElement).key || Math.random().toString();
            return <AnimatedListItem key={key}>{item}</AnimatedListItem>;
          })}
        </AnimatePresence>
      </div>
    );
  },
);

export function AnimatedListItem({ children }: { children: React.ReactNode; key?: React.Key }) {
  const animations = {
    initial: { scale: 0.8, opacity: 0, y: -20 },
    animate: { scale: 1, opacity: 1, y: 0, originY: 0 },
    exit: { scale: 0.8, opacity: 0, y: 20 },
    transition: { type: 'spring', stiffness: 350, damping: 40 },
  };

  return (
    <motion.div {...animations} layout className="w-full h-full">
      {children}
    </motion.div>
  );
}
