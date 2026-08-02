import { QuartzComponent, QuartzComponentConstructor } from "./types"

const PhotoSwipe: QuartzComponent = () => {
  return <div id="photoswipe-test">PHOTOSWIPE HERE</div>
}

PhotoSwipe.afterDOMLoaded = `
  console.log("PHOTOSWIPE COMPONENT LOADED")
`

export default (() => PhotoSwipe) satisfies QuartzComponentConstructor