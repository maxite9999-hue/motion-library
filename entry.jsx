import React from 'react';
import {Composition,registerRoot} from 'remotion';
import {specs} from './recipes.mjs';
import {MotionTemplate} from './Composition.jsx';
registerRoot(()=>Object.entries(specs).map(([id,s])=><Composition id={id} key={id} component={MotionTemplate} width={1280} height={720} fps={30} durationInFrames={s.frames} defaultProps={{id}}/>));
