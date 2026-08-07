import { QuartzComponent, QuartzComponentConstructor } from "./types"
// @ts-ignore
import photoswipeScript from "./scripts/photoswipe.inline"
// @ts-ignore
import photoswipeStyles from "photoswipe/style.css"

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
