/* -*- mode: C; c-basic-offset: 2; indent-tabs-mode: nil; -*- */
/*
 * Copyright (C) 2009-2012  Tiger Soldier <tigersoldi@gmail.com>
 *
 * This file is part of OSD Lyrics.
 * OSD Lyrics is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * OSD Lyrics is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with OSD Lyrics.  If not, see <https://www.gnu.org/licenses/>.
 */
#include <stdlib.h>
#include "ol_lyric_candidate_selector.h"
#include "ol_gui.h"
#include "ol_config_proxy.h"
#include "ol_lyric_candidate_list.h"
#include "ol_debug.h"

static GtkWidget *window = NULL;
static GtkTreeView *list = NULL;
static GtkButton *download_button = NULL;
static OlMetadata *metadata = NULL;
static OlLrcFetchUiDownloadFunc download_func;

static void ol_lrc_fetch_select_changed (GtkTreeSelection *selection, gpointer data);
static gboolean internal_init ();
gboolean ol_lrc_fetch_cancel (GtkWidget *widget, gpointer data);

gboolean
ol_lyric_candidate_selector_cancel (GtkWidget *widget, gpointer data)
{
  ol_log_func ();
  if (window != NULL)
    gtk_widget_hide (window);
  return TRUE;
}

gboolean
ol_lyric_candidate_selector_download (GtkWidget *widget, gpointer data)
{
  ol_log_func ();

  OlLyricSourceCandidate *candidate;
  candidate = ol_lyric_candidate_list_get_selected (list);
  if (candidate)
  {
    if (download_func)
      download_func (candidate, metadata);
  }
  OlConfigProxy *config = ol_config_proxy_get_instance ();
  GtkToggleButton *prompt_btn = GTK_TOGGLE_BUTTON (ol_gui_get_widget ("choose-do-not-prompt"));
  if (prompt_btn != NULL && config != NULL)
  {
    if (gtk_toggle_button_get_active (prompt_btn))
    {
      ol_config_proxy_set_bool (config,
                                "Download/download-first-lyric",
                                TRUE);
    }
  }
  gtk_widget_hide (window);
  return TRUE;
}

// change
/*
  get best match
 */
OlLyricSourceCandidate *
ol_lyric_candidate_list_get_best (GList *candidates)
{
  char *_title = ol_metadata_get_search_title (metadata);
  if (_title == NULL || strlen (_title) == 0)
  {
    return NULL;
  }
  char *_artist = ol_metadata_get_search_artist (metadata);
  char *title = g_ascii_strdown (_title, -1);
  char *artist = g_ascii_strdown (_artist, -1);

  OlLyricSourceCandidate *c = NULL;
  for (; candidates; candidates = g_list_next (candidates))
  {
    OlLyricSourceCandidate *candidate = OL_LYRIC_SOURCE_CANDIDATE (candidates->data);
    if (candidate == NULL) continue;
    const gchar * _t = ol_lyric_source_candidate_get_title (candidate);
    const gchar * _a = ol_lyric_source_candidate_get_artist (candidate);
    char *t = g_ascii_strdown (_t, -1);
    char *a = g_ascii_strdown (_a, -1);
    if (g_str_equal (title, t))
    {
      c = candidate;
      if (artist == NULL || strlen (artist) == 0 || g_str_equal (artist, a))
      {
        g_free (t);
        g_free (a);
        break;
      }
    }
    g_free (t);
    g_free (a);
  }
  g_free (_title);
  g_free (_artist);
  g_free (title);
  g_free (artist);

  return c;
}

/*
  download best match, if not found call default download
 */
gboolean
ol_lyric_candidate_best_download (GList *candidates)
{
  ol_log_func ();

  OlLyricSourceCandidate *candidate;
  candidate = ol_lyric_candidate_list_get_best (candidates);
  if (candidate)
  {
    if (download_func)
      download_func (candidate, metadata);
  }
  else {
    return ol_lyric_candidate_selector_download (GTK_WIDGET (download_button), NULL);
  }

  OlConfigProxy *config = ol_config_proxy_get_instance ();
  GtkToggleButton *prompt_btn = GTK_TOGGLE_BUTTON (ol_gui_get_widget ("choose-do-not-prompt"));
  if (prompt_btn != NULL && config != NULL)
  {
    if (gtk_toggle_button_get_active (prompt_btn))
    {
      ol_config_proxy_set_bool (config,
                                "Download/download-first-lyric",
                                TRUE);
    }
  }
  gtk_widget_hide (window);
  return TRUE;
}
// change end

static void
ol_lrc_fetch_select_changed (GtkTreeSelection *selection, gpointer data)
{
  ol_log_func ();
  if (download_button != NULL)
    gtk_widget_set_sensitive (GTK_WIDGET (download_button),
                              gtk_tree_selection_get_selected (selection, NULL, NULL));
}

static gboolean
internal_init ()
{
  ol_log_func ();
  if (window == NULL)
  {
    window = ol_gui_get_widget ("downloaddialog");
    if (window == NULL)
      return FALSE;
    g_signal_connect (G_OBJECT (window),
                      "delete-event",
                      G_CALLBACK (gtk_widget_hide_on_delete),
                      NULL);
  }
  if (download_button == NULL)
  {
    download_button = GTK_BUTTON (ol_gui_get_widget ("lrc-download"));
  }
  if (list == NULL)
  {
    list = GTK_TREE_VIEW (ol_gui_get_widget ("candidate-list"));
    ol_lyric_candidate_list_init (list,
                                  G_CALLBACK (ol_lrc_fetch_select_changed));
  }
  return TRUE;
}

void
ol_lyric_candidate_selector_show (GList *candidates,
                                  const OlMetadata *_metadata,
                                  OlLrcFetchUiDownloadFunc _download_func)
{
  ol_log_func ();
  if (window == NULL && !internal_init ())
    return;
  if (candidates == NULL || _download_func == NULL)
  {
    gtk_widget_hide (window);
    return;
  }

  // change to keep whole list
  GList * _candidates = candidates;
  // change end

  ol_lyric_candidate_list_set_list (list, candidates);
  if (metadata == NULL)
    metadata = ol_metadata_new ();
  ol_metadata_copy (metadata, _metadata);
  download_func = _download_func;
  gboolean prompt = TRUE;
  OlConfigProxy *config = ol_config_proxy_get_instance ();
  if (config != NULL)
    prompt = ol_config_proxy_get_bool (config, "Download/download-first-lyric");
  if (prompt || g_list_next (candidates) == NULL)

    // change to download best match
    ol_lyric_candidate_best_download (_candidates);
    // ol_lyric_candidate_selector_download (GTK_WIDGET (download_button), NULL);
    // change end

  else
    gtk_widget_show (window);
}
