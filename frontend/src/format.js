import { marked } from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js/lib/core';
import { escapeHtml } from "./utils.js";


// Manually whitelisting used languages to drastically reduce hljs bundle size.
hljs.registerLanguage('python', require('highlight.js/lib/languages/python'));
hljs.registerLanguage('css', require('highlight.js/lib/languages/css'));
hljs.registerLanguage('xml', require('highlight.js/lib/languages/xml'));
hljs.registerLanguage('javascript', require('highlight.js/lib/languages/javascript'));
hljs.registerLanguage('c', require('highlight.js/lib/languages/c'));
hljs.registerLanguage('cpp', require('highlight.js/lib/languages/cpp'));
hljs.registerLanguage('ini', require('highlight.js/lib/languages/ini'));
hljs.registerLanguage('yaml', require('highlight.js/lib/languages/yaml'));
hljs.registerLanguage('json', require('highlight.js/lib/languages/json'));
hljs.registerLanguage('php', require('highlight.js/lib/languages/php'));
hljs.registerLanguage('rust', require('highlight.js/lib/languages/rust'));
hljs.registerLanguage('java', require('highlight.js/lib/languages/java'));


// Number of lines to keep in preview.
const previewLines = 10;

/**
 * Custom code renderer for marked.js to stop it using <pre><code> and if a language is
 * specified use our language highlighter instead.
 */
const renderer = {
    code({ text, lang }) {
        var ext = "txt";

        if (lang == "python") {
            ext = "py";
        } else if (lang == "text") {
            // Explicit, but it should fall through anyway.
            ext = "txt";
        } else if (lang == "markdown") {
            // Don't recursively render markdown, it should be code.
            ext = "txt";
        } else if (lang) {
            ext = lang;
        }

        // Make sure if code is truncated, to truncate it.
        var truncated = false;
        if (text.includes("\n\n!!!!!\n\n")) {
            const bits = text.split("\n\n!!!!!\n\n");
            text = bits[0];
            truncated = true;
        }

        const formatted = formatText(ext, text);

        // If we truncated mid-code, make sure the rest doesn't appear.
        if (truncated) {
            return formatted + "<p>!!!!!</p>";
        } else {
            return formatted;
        }
    }
};

marked.use({ renderer });

/**
 * Helper to ensure spacing and newlines work within manually-formatted HTML.
 */
const preserveSpacing = function( html ) {
    html = html.replaceAll("\n ", "<br />&nbsp;");
	html = html.replaceAll("\n", "<br />");
	html = html.replaceAll("  ", "&nbsp;&nbsp;");
	html = html.replaceAll("\t", "&nbsp;&nbsp;&nbsp;&nbsp;");
	return html;
}

/**
 * Formats a text attachment for display.
 */
const formatText = function( extension, text ) {
	if ( extension == "md" ) {
		// Markdown formatting.
		return DOMPurify.sanitize(marked.parse(text));
	} else if( extension == "py" ) {
		let html = hljs.highlight(text, {language: 'py', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if( extension == "css" ) {
		let html = hljs.highlight(text, {language: 'css', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if(
		extension == "htm" || extension == "html" ||
		extension == "xhtml" || extension == "html5" ||
		extension == "shtml"
	) {
		let html = hljs.highlight(text, {language: 'html', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if( extension == "js" || extension == "jsx" ) {
		let html = hljs.highlight(text, {language: 'js', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if( extension == "c" || extension == "h" ) {
		let html = hljs.highlight(text, {language: 'c', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if(
		extension == "cpp" || extension == "hpp" ||
		extension == "cc" || extension == "hh" ||
		extension == "cxx" || extension == "hxx" ||
		extension == "c++" || extension == "h++"
	) {
		let html = hljs.highlight(text, {language: 'c++', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if( extension == "ini" ) {
		let html = hljs.highlight(text, {language: 'ini', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if( extension == "toml" ) {
		let html = hljs.highlight(text, {language: 'toml', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if( extension == "yaml" || extension == "yml" ) {
		let html = hljs.highlight(text, {language: 'yaml', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if( extension == "json" ) {
		let html = hljs.highlight(text, {language: 'json', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if(
		extension == "php" || extension == "php3" ||
		extension == "php4" || extension == "php5"
	) {
		let html = hljs.highlight(text, {language: 'php', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if( extension == "rs" ) {
		let html = hljs.highlight(text, {language: 'rust', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else if( extension == "java" ) {
		let html = hljs.highlight(text, {language: 'java', ignoreIllegals: true}).value;
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	} else {
		// Raw text formatting.
		let html = escapeHtml(text);
		return '<span class="plaintext">' + preserveSpacing(html) + '</span>';
	}
}

/**
 * Shortens a text attachment for collapsed preview.
 */
const shortenText = function( extension, lines ) {
    if ( extension == "md" ) {
        // Markdown formatting, have to keep definitions which can be at the end.
        var kept = lines.slice(0, previewLines).join("\n");
        kept = kept.replaceAll("!!!!!", "&excl;&excl;&excl;&excl;&excl;");
        kept += "\n\n!!!!!\n\n";
        kept += lines.slice(previewLines).join("\n");

        var formatted = formatText(extension, kept);
        return formatted.split("<p>!!!!!</p>")[0];
    } else {
        return formatText(extension, lines.slice(0, previewLines).join("\n"));
    }
}

export {
    previewLines,
    preserveSpacing,
    formatText,
    shortenText,
};
