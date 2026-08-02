import PhotoSwipeLightbox from "photoswipe/lightbox"
import "photoswipe/style.css"

document.querySelectorAll("img").forEach((img) => {
  img.parentElement?.classList.add("pswp-gallery")
})

const lightbox = new PhotoSwipeLightbox({
  gallery: ".pswp-gallery",
  children: "img",
  pswpModule: () => import("photoswipe"),
})

lightbox.init()