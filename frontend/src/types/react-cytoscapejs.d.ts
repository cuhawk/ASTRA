// Ambient module declaration for react-cytoscapejs (no upstream types as of 2.0.0).
declare module "react-cytoscapejs" {
  import type { CSSProperties, ComponentType } from "react";
  import type {
    Core,
    ElementDefinition,
    LayoutOptions,
    StylesheetCSS,
  } from "cytoscape";

  export interface CytoscapeComponentProps {
    elements: ElementDefinition[];
    stylesheet?: StylesheetCSS[];
    layout?: LayoutOptions | Record<string, unknown>;
    style?: CSSProperties;
    className?: string;
    zoom?: number;
    pan?: { x: number; y: number };
    minZoom?: number;
    maxZoom?: number;
    zoomingEnabled?: boolean;
    userZoomingEnabled?: boolean;
    panningEnabled?: boolean;
    userPanningEnabled?: boolean;
    boxSelectionEnabled?: boolean;
    autoungrabify?: boolean;
    autolock?: boolean;
    autounselectify?: boolean;
    headless?: boolean;
    cy?: (cy: Core) => void;
  }

  const CytoscapeComponent: ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}
