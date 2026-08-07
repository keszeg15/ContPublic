import PhotoSwipeCore from "photoswipe"
import PhotoSwipeLightbox from "photoswipe/lightbox"

type Slide = {
  src: string
  width: number
  height: number
  alt: string
}

/** Images already wrapped in a link keep their link behaviour. */
function zoomableImages(container: HTMLElement): HTMLImageElement[] {
  return Array.from(container.querySelectorAll<HTMLImageElement>("img")).filter(
    (img) => !img.closest("a"),
  )
}

function toSlide(img: HTMLImageElement): Slide {
  return {
    src: img.currentSrc || img.src,
    width: img.naturalWidth || img.width,
    height: img.naturalHeight || img.height,
    alt: img.alt,
  }
}

document.addEventListener("nav", () => {
  const container = document.querySelector<HTMLElement>("article")
  if (!container) return

  const lightbox = new PhotoSwipeLightbox({
    pswpModule: PhotoSwipeCore,
    bgOpacity: 0.9,
  })
  lightbox.init()

  const onClick = (ev: MouseEvent) => {
    const target = ev.target
    if (!(target instanceof HTMLImageElement)) return

    const images = zoomableImages(container)
    const index = images.indexOf(target)
    if (index < 0) return

    const slides = images.map(toSlide)

    // Without real dimensions PhotoSwipe cannot size the slide, so leave the click alone
    if (!slides[index].width || !slides[index].height) return

    ev.preventDefault()
    lightbox.loadAndOpen(index, slides)
  }

  container.addEventListener("click", onClick)
  window.addCleanup(() => {
    container.removeEventListener("click", onClick)
    lightbox.destroy()
  })
})
