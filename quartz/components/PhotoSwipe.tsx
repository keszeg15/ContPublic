import { QuartzComponent, QuartzComponentConstructor } from "./types"

const PhotoSwipe: QuartzComponent = () => {
  return null
}

PhotoSwipe.afterDOMLoaded = `
  document.querySelectorAll("article img").forEach((img) => {
    const link = img.closest("a")

    if (!link) {
      const wrapper = document.createElement("a")
      wrapper.href = img.src
      img.parentNode?.insertBefore(wrapper, img)
      wrapper.appendChild(img)
    }

    img.parentElement?.classList.add("pswp-gallery")
  })

  document.querySelectorAll(".pswp-gallery img").forEach((img) => {
    img.setAttribute("data-pswp-width", img.naturalWidth)
    img.setAttribute("data-pswp-height", img.naturalHeight)
  })

  import("./scripts/photoswipe.inline.ts")
`

export default (() => PhotoSwipe) satisfies QuartzComponentConstructor