/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-11
 * Time: 13:56
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

import { PaletteOptions, createTheme, css } from "@mui/material/styles";

export type AllowedTheme = NonNullable<PaletteOptions["mode"]>;

export const lightTheme = createTheme({
  palette: {
    primary: { main: "#007AFF" },
    secondary: { main: "#f04444" },
    mode: "light",
  },
});

export const darkTheme = createTheme({
  palette: {
    primary: { main: "#ffa500" },
    secondary: { main: "#f04444" },
    mode: "dark",
  },
});

export const globalStyles = css`
  :root {
    body {
      background-color: #fff;
      color: #121212;
    }
  }
  [data-theme="dark"] {
    body {
      background-color: #121212;
      color: #fff;
    }
  }
`;
