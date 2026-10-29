import { createTheme, type MantineColorsTuple } from '@mantine/core';

// PRD 第 8 節：主色焦糖 #B4632E、背景米白 #FAF6F0、文字深咖啡 #3B2F2A、輔色橄欖綠 #5F7A45、錯誤 #B3261E
const caramel: MantineColorsTuple = [
  '#fbf1ea',
  '#f1dccd',
  '#e5bfa4',
  '#d9a07a',
  '#cc8654',
  '#c0753d',
  '#b4632e',
  '#9b5324',
  '#82441c',
  '#693613',
];
const olive: MantineColorsTuple = [
  '#f0f5ea',
  '#dde8d0',
  '#c3d5ae',
  '#a7c188',
  '#8fb066',
  '#7a9f4f',
  '#5f7a45',
  '#4f6738',
  '#40542d',
  '#314122',
];

export const theme = createTheme({
  primaryColor: 'caramel',
  primaryShade: 6,
  colors: { caramel, olive },
  fontFamily: '"Noto Sans TC", system-ui, sans-serif',
  defaultRadius: 'md',
  black: '#3B2F2A',
  headings: { fontWeight: '700' },
});

export const COLORS = {
  background: '#FAF6F0',
  text: '#3B2F2A',
  success: '#5F7A45',
  error: '#B3261E',
};
