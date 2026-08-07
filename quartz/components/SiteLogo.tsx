import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { joinSegments, pathToRoot } from "../util/path"

/**
 * Logo for the top of the left sidebar, linking back to the home page.
 *
 * The image lives at quartz/static/logo.png, which the Static emitter copies to
 * /static. The path is resolved relative to the current page so it also works
 * when the site is served from a subdirectory.
 *
 * Styling lives in custom.scss rather than here: component CSS is wrapped in
 * @layer quartz-base, so it would lose to the unlayered `img` rule in that file.
 */
const SiteLogo: QuartzComponent = ({ fileData, cfg }: QuartzComponentProps) => {
  const baseDir = pathToRoot(fileData.slug!)

  return (
    <a href={baseDir} class="site-logo">
      <img src={joinSegments(baseDir, "static/logo.png")} alt={cfg.pageTitle} />
    </a>
  )
}

export default (() => SiteLogo) satisfies QuartzComponentConstructor
