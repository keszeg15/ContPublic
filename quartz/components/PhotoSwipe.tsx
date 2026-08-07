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

article a img {
  cursor: pointer;
}
`,
]

PhotoSwipe.afterDOMLoaded = photoswipeScript

export default (() => PhotoSwipe) satisfies QuartzComponentConstructor
