import { QuartzComponent, QuartzComponentConstructor } from "./types"

const PhotoSwipe: QuartzComponent = () => {
  return null
}

PhotoSwipe.afterDOMLoaded = `
  import("./scripts/photoswipe.inline.ts")
`

export default (() => PhotoSwipe) satisfies QuartzComponentConstructor