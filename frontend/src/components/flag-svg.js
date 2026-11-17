import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

export function FlagSVG({
  svgString,
  className,
  size = '1rem',
  allowExpand = false,
}) {
  if (!svgString) return null;

  // Extract width and height from SVG string if they exist
  const widthMatch = svgString.match(/width="(\d+)"/);
  const heightMatch = svgString.match(/height="(\d+)"/);
  const width = widthMatch ? parseInt(widthMatch[1]) : 24;
  const height = heightMatch ? parseInt(heightMatch[1]) : 24;

  const modifiedSvgString = svgString
    .replace(/x2="([\-\w]+) y1="([\-\w]+)"/g, 'x2="$1" y2="$2"')
    .replace(/<!-- ([\w\s]+) \*\//g, '<!-- $1 -->')
    .replace(/(<svg[^>]*)>/, (match, p1) => {
      const cleanedAttributes = p1.replace(/viewBox="[^"]*"/, '');
      return `${cleanedAttributes} viewBox="0 0 ${width} ${height}">`;
    });

  // Add safety check before creating Blob
  if (!modifiedSvgString.includes('</svg>')) {
    console.warn('Invalid SVG string detected');
    return null;
  }

  // Treat AI/browser-provided SVG as an isolated image, NEVER injected DOM.
  // Image-context SVG cannot execute event handlers/scripts in the game origin.
  const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(modifiedSvgString)}`;
  const SvgComponent = (
    <img
      src={url}
      alt="Nation flag"
      className={className}
      style={{ height: size, width: 'auto', display: 'inline-block', verticalAlign: 'middle' }}
    />
  );

  if (!allowExpand) {
    return SvgComponent;
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <div className="cursor-pointer">{SvgComponent}</div>
      </DialogTrigger>
      <DialogContent className="max-w-[90vw] max-h-[90vh]">
        <DialogTitle className="mb-4">Flag</DialogTitle>
        <img
          src={url}
          alt="Expanded nation flag"
          className="mx-auto block h-auto w-auto max-w-full"
          style={{ maxHeight: '80vh' }}
        />
      </DialogContent>
    </Dialog>
  );
}
