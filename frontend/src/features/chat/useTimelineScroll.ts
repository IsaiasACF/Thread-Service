import { useEffect, useRef } from 'react';

// Follow new activity only while the reader is already at the bottom.
export function useTimelineScroll(lastId?: string) {
  const container = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const force = useRef(false);
  useEffect(() => {
    const node = container.current;
    if (!node) return;
    const onScroll = () => { follow.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80; };
    const resize = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => {
      if (follow.current) node.scrollTop = node.scrollHeight;
    });
    node.addEventListener('scroll', onScroll);
    resize?.observe(node);
    return () => { node.removeEventListener('scroll', onScroll); resize?.disconnect(); };
  }, []);
  useEffect(() => {
    if (container.current && (follow.current || force.current)) container.current.scrollTop = container.current.scrollHeight;
    force.current = false;
  }, [lastId]);
  return { container, revealNext: () => { force.current = true; } };
}
