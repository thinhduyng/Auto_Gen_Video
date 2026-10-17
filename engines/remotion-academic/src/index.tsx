import React from "react";
import { Composition, registerRoot } from "remotion";
import { Academic } from "./Academic";
import { Props } from "./lib";

const FPS = 30;

const defaultProps: Props = {
  audio: "",
  data: { meta: { series: "", ep: null, total: null, title: "" }, duration: 3, scenes: [], words: [], phrases: [], diagrams: {} },
};

const Root: React.FC = () => (
  <Composition
    id="Academic"
    component={Academic}
    width={1080}
    height={1920}
    fps={FPS}
    durationInFrames={FPS * 3}
    defaultProps={defaultProps}
    calculateMetadata={({ props }) => ({ durationInFrames: Math.max(1, Math.ceil(props.data.duration * FPS - 1e-7)) })}
  />
);

registerRoot(Root);
