(* structure.md: copy a form from profiles/poem/forms/ and edit it, or write your own.
   See references/psg.md for the grammar. *)
poem {
  named "villanelle";
  refrain R1 at 1, 6, 12, 18;
  refrain R2 at 3, 9, 15, 19;
  stanza (tercet, 5, A B A) {
    line (iamb 5, stop, A) { image["<what this line holds>"] }
    line (iamb 5, stop, B) { image["<what this line holds>"] }
    line (iamb 5, stop, A) { image["<what this line holds>"] }
  }
  stanza (quatrain, 1, A B A A) {
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, B) { }
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, A) { }
  }
}
