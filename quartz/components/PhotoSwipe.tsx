import { QuartzComponent, QuartzComponentConstructor } from "./types"

const PhotoSwipe: QuartzComponent = () => {
  return null
}

PhotoSwipe.afterDOMLoaded = `
  console.log("PHOTOSWIPE COMPONENT LOADED")
`

export default (() => PhotoSwipe) satisfies QuartzComponentConstructor