import { QuartzComponent, QuartzComponentConstructor } from "./types"
// @ts-ignore
import photoswipeScript from "./scripts/photoswipe.inline"
// Vendored from photoswipe 5.4.4. Importing the package's own stylesheet does not
// work: the main build marks node_modules as external, so Node resolves it at
// runtime and cannot load a .css file.
import photoswipeStyles from "./styles/photoswipe.scss"

const PhotoSwipe: QuartzComponent = () => {
  return null
}

PhotoSwipe.css = [
  photoswipeStyles,
  `
article img {
  cursor: zoom-in;
}

/* Images that link somewhere else keep navigating, so they keep the link cursor. */
article a:not([href$=".avif"]):not([href$=".gif"]):not([href$=".jpg"]):not([href$=".jpeg"]):not([href$=".png"]):not([href$=".svg"]):not([href$=".webp"]) img {
  cursor: pointer;
}
`,
]

PhotoSwipe.afterDOMLoaded = photoswipeScript

export default (() => PhotoSwipe) satisfies QuartzComponentConstructor
