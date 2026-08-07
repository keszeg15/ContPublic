import PhotoSwipeCore from "photoswipe"
import PhotoSwipeLightbox from "photoswipe/lightbox"

type Slide = {
  src: string
  width: number
  height: number
  alt: string
}

/** An anchor around an image only keeps its link behaviour when it points somewhere else. */
const IMAGE_HREF = /\.(avif|gif|jpe?g|png|svg|webp)(?:[?#]|$)/i

/**
 * The rendered note body is an <article>, but fall back to the centre column so a
 * change in the content-page plugin cannot silently switch zooming off.
 */
function contentRoot(from: Element): HTMLElement | null {
  return from.closest<HTMLElement>("article") ?? from.closest<HTMLElement>(".center")
}

/** Returns the URL to open full size, or null when the image should not be zoomable. */
function fullSizeSrc(img: HTMLImageElement): string | null {
  const anchor = img.closest("a")
  if (!anchor) {
    return img.currentSrc || img.src
  }

  // Quartz links an image to itself in some embeds; anything else is real navigation.
  return IMAGE_HREF.test(anchor.getAttribute("href") ?? "") ? anchor.href : null
}

function zoomableImages(root: HTMLElement): HTMLImageElement[] {
  return Array.from(root.querySelectorAll<HTMLImageElement>("img")).filter(
    (img) => fullSizeSrc(img) !== null,
  )
}

function toSlide(img: HTMLImageElement): Slide {
  return {
    src: fullSizeSrc(img)!,
    width: img.naturalWidth || img.width,
    height: img.naturalHeight || img.height,
    alt: img.alt,
  }
}

let lightbox: PhotoSwipeLightbox | undefined

function getLightbox(): PhotoSwipeLightbox {
  if (!lightbox) {
    lightbox = new PhotoSwipeLightbox({
      pswpModule: PhotoSwipeCore,
      bgOpacity: 0.9,
    })
    lightbox.init()
  }
  return lightbox
}

// Delegated from document so the handler survives SPA navigation without needing
// to be re-attached on every "nav", and so it cannot be missed if the body of the
// page is replaced underneath us.
document.addEventListener("click", (ev) => {
  const target = ev.target
  if (!(target instanceof HTMLImageElement)) return

  // Leave modified clicks alone so opening in a new tab still works.
  if (ev.defaultPrevented || ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey) return

  const root = contentRoot(target)
  if (!root) {
    console.debug("photoswipe: image is outside the content area, ignoring click")
    return
  }

  const images = zoomableImages(root)
  const index = images.indexOf(target)
  if (index < 0) {
    console.debug("photoswipe: image is not zoomable (linked elsewhere), ignoring click")
    return
  }

  const slides = images.map(toSlide)

  // PhotoSwipe cannot size a slide without dimensions, so leave broken images be.
  if (!slides[index].width || !slides[index].height) {
    console.debug("photoswipe: image has no dimensions yet, ignoring click")
    return
  }

  ev.preventDefault()
  getLightbox().loadAndOpen(index, slides)
})
