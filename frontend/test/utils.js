import { containsStandaloneText, highlightStandaloneText } from '../src/utils.js';

test('containsStandaloneText empty string', () => {
    expect(containsStandaloneText("", "@test")).toBe(false);
    expect(highlightStandaloneText("", "@test", "[[", "]]")).toBe("");
});

test('containsStandaloneText non-containing string', () => {
    expect(containsStandaloneText("this is a random string", "@test")).toBe(false);
    expect(highlightStandaloneText("this is a random string", "@test", "[[", "]]")).toBe("this is a random string");
});

test('containsStandaloneText containing only string', () => {
    expect(containsStandaloneText("@test", "@test")).toBe(true);
    expect(highlightStandaloneText("@test", "@test", "[[", "]]")).toBe("[[@test]]");
});

test('containsStandaloneText begin or end string', () => {
    expect(containsStandaloneText("@test 123", "@test")).toBe(true);
    expect(highlightStandaloneText("@test 123", "@test", "[[", "]]")).toBe("[[@test]] 123");
    expect(containsStandaloneText("123 @test", "@test")).toBe(true);
    expect(highlightStandaloneText("123 @test", "@test", "[[", "]]")).toBe("123 [[@test]]");
});

test('containsStandaloneText containing only substring', () => {
    expect(containsStandaloneText("@testing", "@test")).toBe(false);
    expect(highlightStandaloneText("@testing", "@test", "[[", "]]")).toBe("@testing");
});

test('containsStandaloneText containing string', () => {
    expect(containsStandaloneText("hello @test how are you", "@test")).toBe(true);
    expect(highlightStandaloneText("hello @test how are you", "@test", "[[", "]]")).toBe("hello [[@test]] how are you");
});

test('containsStandaloneText containing substring', () => {
    expect(containsStandaloneText("hello @testing how are you", "@test")).toBe(false);
    expect(highlightStandaloneText("hello @testing how are you", "@test", "[[", "]]")).toBe("hello @testing how are you");
});

test('containsStandaloneText containing string punctuation', () => {
    // Standard punctuation.
    expect(containsStandaloneText("hello @test!", "@test")).toBe(true);
    expect(highlightStandaloneText("hello @test!", "@test", "[[", "]]")).toBe("hello [[@test]]!");

    expect(containsStandaloneText("hello @test?", "@test")).toBe(true);
    expect(highlightStandaloneText("hello @test?", "@test", "[[", "]]")).toBe("hello [[@test]]?");

    expect(containsStandaloneText("hello @test.", "@test")).toBe(true);
    expect(highlightStandaloneText("hello @test.", "@test", "[[", "]]")).toBe("hello [[@test]].");

    expect(containsStandaloneText("hello @test, hello!", "@test")).toBe(true);
    expect(highlightStandaloneText("hello @test, hello!", "@test", "[[", "]]")).toBe("hello [[@test]], hello!");

    expect(containsStandaloneText("hello @test; hello!", "@test")).toBe(true);
    expect(highlightStandaloneText("hello @test; hello!", "@test", "[[", "]]")).toBe("hello [[@test]]; hello!");

    expect(containsStandaloneText("hello @test: hello!", "@test")).toBe(true);
    expect(highlightStandaloneText("hello @test: hello!", "@test", "[[", "]]")).toBe("hello [[@test]]: hello!");

    // Parenthesis of sorts.
    expect(containsStandaloneText("hello (@test) how are you?", "@test")).toBe(true);
    expect(highlightStandaloneText("hello (@test) how are you?", "@test", "[[", "]]")).toBe("hello ([[@test]]) how are you?");
    expect(containsStandaloneText("hello [@test] how are you?", "@test")).toBe(true);
    expect(highlightStandaloneText("hello [@test] how are you?", "@test", "[[", "]]")).toBe("hello [[[@test]]] how are you?");
    expect(containsStandaloneText("hello {@test} how are you?", "@test")).toBe(true);
    expect(highlightStandaloneText("hello {@test} how are you?", "@test", "[[", "]]")).toBe("hello {[[@test]]} how are you?");

    // Specifically for upcoming feature where names are clickable to go to profiles even if they're not your mention.
    expect(containsStandaloneText("hello >@test< how are you?", "@test")).toBe(true);
    expect(highlightStandaloneText("hello >@test< how are you?", "@test", "[[", "]]")).toBe("hello >[[@test]]< how are you?");

    // Make sure that a user with a dot in their name can be recognized.
    expect(containsStandaloneText("hello @test.dotted.", "@test.dotted")).toBe(true);
    expect(highlightStandaloneText("hello @test.dotted.", "@test.dotted", "[[", "]]")).toBe("hello [[@test.dotted]].");
});

test('containsStandaloneText containing quote punctuation', () => {
    // Make sure that somebody can use apostrophes around names.
    expect(containsStandaloneText("thanks to @test's post", "@test")).toBe(true);
    expect(highlightStandaloneText("thanks to @test's post", "@test", "[[", "]]")).toBe("thanks to [[@test]]'s post");
    expect(containsStandaloneText("thanks to @test&apos;s post", "@test")).toBe(true);
    expect(highlightStandaloneText("thanks to @test&apos;s post", "@test", "[[", "]]")).toBe("thanks to [[@test]]&apos;s post");

    // Make sure we can quote around names as well.
    expect(containsStandaloneText("quoting \"@test\" here", "@test")).toBe(true);
    expect(highlightStandaloneText("quoting \"@test\" here", "@test", "[[", "]]")).toBe("quoting \"[[@test]]\" here");
    expect(containsStandaloneText("quoting '@test' here", "@test")).toBe(true);
    expect(highlightStandaloneText("quoting '@test' here", "@test", "[[", "]]")).toBe("quoting '[[@test]]' here");
    expect(containsStandaloneText("quoting \"thing with @test\" here", "@test")).toBe(true);
    expect(highlightStandaloneText("quoting \"thing with @test\" here", "@test", "[[", "]]")).toBe("quoting \"thing with [[@test]]\" here");
    expect(containsStandaloneText("quoting \"@test with thing\" here", "@test")).toBe(true);
    expect(highlightStandaloneText("quoting \"@test with thing\" here", "@test", "[[", "]]")).toBe("quoting \"[[@test]] with thing\" here");

    // Make sure things also work with escaped text.
    expect(containsStandaloneText("quoting &quot;@test&quot; here", "@test")).toBe(true);
    expect(highlightStandaloneText("quoting &quot;@test&quot; here", "@test", "[[", "]]")).toBe("quoting &quot;[[@test]]&quot; here");
});
