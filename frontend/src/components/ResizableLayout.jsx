import { useRef, useCallback } from 'react';

/** Vertical resize handle — dragging left/right to resize side panels */
export function VerticalResizeHandle({ onDrag }) {
  const isDragging = useRef(false);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMouseMove = (e) => {
      if (isDragging.current) onDrag(e.clientX);
    };
    const onMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [onDrag]);

  return (
    <div
      onMouseDown={handleMouseDown}
      className="w-1.5 cursor-col-resize group flex items-center justify-center shrink-0
                 hover:bg-ocean-500/20 transition-colors"
    >
      <div className="w-0.5 h-8 bg-gray-700 rounded-full group-hover:bg-ocean-500 transition-colors" />
    </div>
  );
}

/** Horizontal resize handle — dragging up/down to resize top/bottom panels */
export function HorizontalResizeHandle({ onDrag }) {
  const isDragging = useRef(false);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';

    const onMouseMove = (e) => {
      if (isDragging.current) onDrag(e.clientY);
    };
    const onMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [onDrag]);

  return (
    <div
      onMouseDown={handleMouseDown}
      className="h-1.5 cursor-row-resize group flex items-center justify-center shrink-0
                 hover:bg-ocean-500/20 transition-colors"
    >
      <div className="h-0.5 w-8 bg-gray-700 rounded-full group-hover:bg-ocean-500 transition-colors" />
    </div>
  );
}
