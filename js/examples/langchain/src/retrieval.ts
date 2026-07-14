/**
 * Just as a constant function is _technically_ a polynomial, so too is injecting
 * the same information every time _technically_ RAG.
 */
import * as cheerio from "cheerio";
import { RecursiveUrlLoader } from "@langchain/community/document_loaders/web/recursive_url";
import { COLOR } from "./common.js";

const docsUrl = "https://huggingface.co/docs/transformers/index";

export async function retrieveDocs(
  url: string = docsUrl,
  debug = false,
): Promise<string> {
  console.log(`${COLOR.HEADER}📜: Retrieving documents from ${url}${COLOR.ENDC}`);
  const loader = new RecursiveUrlLoader(url, {
    maxDepth: Math.floor(2 / (Number(debug) + 1)), // retrieve fewer docs in debug mode
    extractor: (html: string) => cheerio.load(html).text(),
  });
  const docs = await loader.load();

  // sort the list based on the URLs
  const dSorted = [...docs].sort((a, b) =>
    String(b.metadata.source).localeCompare(String(a.metadata.source)),
  );

  // combine them all together
  let concatenatedContent = dSorted
    .map((doc) => "## " + doc.metadata.source + "\n\n" + doc.pageContent.trim())
    .join("\n\n\n --- \n\n\n");

  console.log(
    `${COLOR.HEADER}📜: Retrieved ${docs.length} documents${COLOR.ENDC}\n` +
      `${COLOR.GREEN}${concatenatedContent.slice(0, 100).trim()}${COLOR.ENDC}`,
  );

  if (debug) {
    console.log(
      `${COLOR.HEADER}📜: Restricting to at most 30,000 characters${COLOR.ENDC}`,
    );
    concatenatedContent = concatenatedContent.slice(0, 30_000);
  }

  return concatenatedContent;
}
