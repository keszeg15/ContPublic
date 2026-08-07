import { loadQuartzConfig, loadQuartzLayout } from "./quartz/plugins/loader/config-loader"
import { componentRegistry } from "./quartz/components/registry"
import CategoryBadge from "./quartz/components/CategoryBadge"
import PhotoSwipe from "./quartz/components/PhotoSwipe"

// Components living in this repo rather than in an installed plugin package.
// The plugin loader only knows how to install directory-based packages, so the
// relative sources in quartz.config.yaml resolve through the registry instead.
// The registry key must match the last path segment of that source.
componentRegistry.register("CategoryBadge", CategoryBadge, "local")
componentRegistry.register("PhotoSwipe", PhotoSwipe, "local")

const config = await loadQuartzConfig()
export default config
export const layout = await loadQuartzLayout()
