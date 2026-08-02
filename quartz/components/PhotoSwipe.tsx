import { QuartzComponent, QuartzComponentConstructor } from "./types"

const PhotoSwipe: QuartzComponent = () => {
  return null
}


PhotoSwipe.afterDOMLoaded = `
  console.log("PHOTOSWIPE COMPONENT LOADED")

  document.querySelectorAll("article img").forEach((img) => {
    console.log("FOUND IMAGE", img)
  })

  import("./scripts/photoswipe.inline.ts")
`


export default (() => PhotoSwipe) satisfies QuartzComponentConstructor