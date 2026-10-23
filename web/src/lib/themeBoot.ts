export const THEME_KEY = "deployar-theme";

/** Runs inline in <head> before paint, so a picked theme never flashes the other one. */
export const THEME_BOOT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
